# nodemanager/core/node.py
import uuid
import psutil
import torch
import platform
import socket
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional, List
import asyncio
import logging
from neuropack.core.distributed_manager import DistributedManager
from pathlib import Path
import websockets
import sys

logger = logging.getLogger(__name__)

@dataclass
class ModelInfo:
    name: str
    type: str  # 'ollama', 'huggingface', 'custom'
    size: int  # Model size in bytes
    loaded: bool
    device: str  # 'cpu', 'cuda:0', etc.
    max_sequence_length: int
    quantization: Optional[str] = None  # '4bit', '8bit', None etc
    shared_layers: Optional[List[str]] = None  # For distributed inference
    current_tasks: int = 0
    memory_used: int = 0  # Current memory usage

@dataclass
class DeviceInfo:
    cpu_count: int
    cpu_freq: float
    total_memory: int
    available_memory: int
    gpu_count: int
    gpu_info: List[Dict]
    hostname: str
    ip_address: str
    platform: str
    loaded_models: Dict[str, Dict] = field(default_factory=dict)
    supported_models: List[str] = field(default_factory=list)
    
    @classmethod
    def gather_info(cls) -> 'DeviceInfo':
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        
        gpu_info = []
        gpu_count = torch.cuda.device_count()
        
        if gpu_count > 0:
            for i in range(gpu_count):
                gpu = torch.cuda.get_device_properties(i)
                gpu_info.append({
                    'name': gpu.name,
                    'total_memory': gpu.total_memory,
                    'major': gpu.major,
                    'minor': gpu.minor
                })
        
        return cls(
            cpu_count=psutil.cpu_count(),
            cpu_freq=psutil.cpu_freq().current if psutil.cpu_freq() else 0.0,
            total_memory=psutil.virtual_memory().total,
            available_memory=psutil.virtual_memory().available,
            gpu_count=gpu_count,
            gpu_info=gpu_info,
            hostname=hostname,
            ip_address=ip,
            platform=platform.system()
        )

    @staticmethod
    def _scan_ollama_models() -> List[str]:
        """Scan for locally available Ollama models"""
        try:
            import subprocess
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            if result.returncode == 0:
                models = []
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    if line.strip():
                        model_name = line.split()[0]
                        models.append(f"ollama/{model_name}")
                return models
        except Exception as e:
            logger.warning(f"Failed to scan Ollama models: {e}")
        return []

    @staticmethod
    def _scan_huggingface_models() -> List[str]:
        """Scan for locally downloaded Hugging Face models"""
        try:
            cache_dir = Path.home() / '.cache' / 'huggingface'
            if cache_dir.exists():
                models = []
                for model_dir in cache_dir.glob('**/pytorch_model.bin'):
                    model_name = model_dir.parent.parent.name
                    models.append(f"huggingface/{model_name}")
                return models
        except Exception as e:
            logger.warning(f"Failed to scan Hugging Face models: {e}")
        return []

class Node:
    def __init__(self, master_host, master_port=8765):
        self.master_host = master_host
        self.master_port = master_port
        self.master_uri = f"ws://{master_host}:{master_port}"
        self.id = str(uuid.uuid4())
        self.device_info = DeviceInfo.gather_info()
        self.is_master = False
        self.connected_nodes: Dict[str, DeviceInfo] = {}
        self.model_registry: Dict[str, Dict[str, ModelInfo]] = {}  # node_id -> {model_name: ModelInfo}
        
        if torch.cuda.is_available():
            self.gpu_manager = DistributedManager()
        else:
            self.gpu_manager = None
        
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'device_info': asdict(self.device_info),
            'is_master': self.is_master
        }
        
    async def start(self):
        """Start the node and connect to master."""
        try:
            # Create tasks for command interface and master connection
            command_task = asyncio.create_task(self._start_command_interface())
            master_task = asyncio.create_task(self._connect_to_master())
            
            # Wait for both tasks
            await asyncio.gather(command_task, master_task)
            
        except Exception as e:
            logger.error(f"Error starting node: {e}", exc_info=True)
            raise
            
    async def _start_command_interface(self):
        """Start the command line interface."""
        try:
            while True:
                command = input("> ")
                if command == "quit":
                    logger.info("Shutting down...")
                    sys.exit(0)
                elif command == "status":
                    self._print_status()
                else:
                    logger.warning(f"Unknown command: {command}")
        except Exception as e:
            logger.error(f"Error in command interface: {e}", exc_info=True)
            raise

    async def _connect_to_master(self):
        """Connect to master node."""
        while True:
            try:
                uri = f"ws://{self.master_host}:{self.master_port}"
                logger.info(f"Connecting to master at {uri}")
                
                async with websockets.connect(uri) as websocket:
                    # Register with master
                    await self._register_with_master(websocket)
                    
                    # Main message loop
                    while True:
                        message = await websocket.recv()
                        await self._handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.error("Connection to master closed, retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error connecting to master: {e}", exc_info=True)
                await asyncio.sleep(5)
                
    async def _register_with_master(self, websocket):
        """Register this node with the master."""
        device_info = self.device_info
        register_msg = {
            'type': 'register',
            'device_info': asdict(device_info)
        }
        await websocket.send(json.dumps(register_msg))
        logger.info(f"Registered with master as node {self.id}")
        
    async def _handle_message(self, message):
        """Handle incoming message from master"""
        try:
            # Ensure message is a string before parsing
            if isinstance(message, dict):
                data = message
            else:
                data = json.loads(message)
            
            msg_type = data.get('type')
            
            if msg_type == 'load_model':
                model_name = data.get('model_name')
                await self.load_model(model_name)
                
            elif msg_type == 'unload_model':
                model_name = data.get('model_name')
                await self.unload_model(model_name)
                
            elif msg_type == 'heartbeat':
                response = json.dumps({
                    'type': 'heartbeat_response',
                    'id': self.id
                })
                await self.websocket.send(response)
                
            elif msg_type == 'status_request':
                status = {
                    'type': 'status_update',
                    'id': self.id,
                    'device_info': asdict(self.device_info)
                }
                await self.websocket.send(json.dumps(status))
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_msg = {
                'type': 'error',
                'id': self.id,
                'error': str(e)
            }
            await self.websocket.send(json.dumps(error_msg))
            
    def _print_status(self):
        """Print current node status."""
        print("\n=== Node Status ===")
        print(f"Node ID: {self.id}")
        print(f"Connected to: {self.master_uri}")
        print(f"Loaded Models: {list(self.device_info.loaded_models.keys())}")
        print("=================\n")

    async def start_master(self):
        """Start master node operations"""
        logger.info("Starting master node...")
        # Initialize master operations
        
    async def connect_to_master(self):
        """Connect to master node"""
        logger.info(f"Connecting to master at {self.master_uri}")
        # Connection logic

    async def load_model(self, model_name: str, device: str = None):
        """Load a model onto this node"""
        try:
            if model_name.startswith('ollama/'):
                await self._load_ollama_model(model_name)
            elif model_name.startswith('huggingface/'):
                await self._load_huggingface_model(model_name, device)
            
            # Update model registry
            model_info = self._get_model_info(model_name)
            self.device_info.loaded_models[model_name] = asdict(model_info)
            await self._notify_master_model_update()
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise

    async def _load_ollama_model(self, model_name: str):
        """Load an Ollama model"""
        import subprocess
        model = model_name.split('/')[1]
        result = subprocess.run(['ollama', 'pull', model], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to pull Ollama model: {result.stderr}")

    async def _load_huggingface_model(self, model_name: str, device: str):
        """Load a Hugging Face model"""
        from transformers import AutoModel
        model = model_name.split('/')[1]
        model = AutoModel.from_pretrained(model)
        if device:
            model.to(device)

    def _get_model_info(self, model_name: str) -> ModelInfo:
        """Get information about a loaded model"""
        # Implementation depends on model type
        pass

    async def _notify_master_model_update(self):
        """Notify master about model changes"""
        if hasattr(self, 'websocket'):
            update = {
                'type': 'model_update',
                'node_id': self.id,
                'models': {
                    name: info 
                    for name, info in self.device_info.loaded_models.items()
                }
            }
            await self.websocket.send(json.dumps(update))

    async def _handle_load_model(self, data):
        # Implementation depends on the load model logic
        pass

    async def _handle_unload_model(self, data):
        # Implementation depends on the unload model logic
        pass

async def main():
    """Main entry point for the node."""
    import argparse
    parser = argparse.ArgumentParser(description='Start a NeuroPack node')
    parser.add_argument('master_ip', help='IP address of the master node')
    parser.add_argument('--port', type=int, default=8765, help='Port of the master node')
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Print system info
    logger.info("\n=== System Information ===")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"CPU: {platform.machine()}")
    logger.info(f"Cores: {psutil.cpu_count()}")
    logger.info(f"CPU Frequency: {psutil.cpu_freq().current/1000:.2f} GHz")
    logger.info("=======================\n")

    # Create and start node
    node = Node(master_host=args.master_ip, master_port=args.port)
    try:
        await node.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running node: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())