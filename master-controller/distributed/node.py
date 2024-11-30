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
            # First check if ollama is installed
            import shutil
            if shutil.which('ollama') is None:
                logger.debug("Ollama not found in PATH")
                return []
                
            import subprocess
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            if result.returncode == 0:
                models = []
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    if line.strip():
                        model_name = line.split()[0]
                        models.append(f"ollama/{model_name}")
                return models
        except FileNotFoundError:
            logger.debug("Ollama command not found")
        except subprocess.SubprocessError as e:
            logger.debug(f"Error running ollama list: {e}")
        except Exception as e:
            logger.debug(f"Failed to scan Ollama models: {e}")
        return []

    @staticmethod
    def _scan_huggingface_models() -> List[str]:
        """Scan for locally downloaded Hugging Face models"""
        try:
            cache_dir = Path.home() / '.cache' / 'huggingface'
            if not cache_dir.exists():
                logger.debug("No HuggingFace cache directory found")
                return []
                
            models = []
            for model_dir in cache_dir.glob('**/pytorch_model.bin'):
                model_name = model_dir.parent.parent.name
                models.append(f"huggingface/{model_name}")
            return models
        except PermissionError:
            logger.debug("Permission denied accessing HuggingFace cache")
        except Exception as e:
            logger.debug(f"Failed to scan HuggingFace models: {e}")
        return []

class Node:
    def __init__(self, master_host, master_port=8765):
        self.master_uri = f"ws://{master_host}:{master_port}"
        self.id = str(uuid.uuid4())
        self.device_info = DeviceInfo.gather_info()
        self.is_master = False
        self.connected = False
        self.websocket = None
        self._reconnect_delay = 5  # seconds
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
        """Start node operations"""
        if self.is_master:
            await self.start_master()
        else:
            await self.connect_to_master()
            
    async def start_master(self):
        """Start master node operations"""
        logger.info("Starting master node...")
        # Initialize master operations
        
    async def connect_to_master(self):
        """Connect to master node"""
        try:
            logger.info(f"Connecting to master at {self.master_uri}")
            async with websockets.connect(self.master_uri) as websocket:
                self.websocket = websocket
                self.connected = True
                
                # Register with master
                register_msg = {
                    'type': 'register',
                    'device_info': asdict(self.device_info)
                }
                await websocket.send(json.dumps(register_msg))
                logger.info("Connected to master")
                
                # Main message loop
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    await self._handle_message(data)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.error("Connection to master closed")
            self.connected = False
            await asyncio.sleep(self._reconnect_delay)
            await self.connect_to_master()  # Try to reconnect
        except Exception as e:
            logger.error(f"Error connecting to master: {e}")
            self.connected = False
            await asyncio.sleep(self._reconnect_delay)
            await self.connect_to_master()  # Try to reconnect

    async def load_model(self, model_name: str, device: str = None):
        """Load a model onto this node"""
        try:
            if model_name.startswith('ollama/'):
                await self._load_ollama_model(model_name)
            elif model_name.startswith('huggingface/'):
                await self._load_huggingface_model(model_name, device)
            
            # Update model registry
            model_info = self._get_model_info(model_name)
            self.device_info.loaded_models[model_name] = model_info
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
                    name: asdict(info) 
                    for name, info in self.device_info.loaded_models.items()
                }
            }
            await self.websocket.send(json.dumps(update))

    async def handle_inference(self, request: dict):
        """Handle inference requests"""
        model_name = request['model']
        prompt = request['prompt']
        is_distributed = request.get('is_distributed', False)
        
        try:
            if is_distributed:
                # Handle distributed inference
                shard_info = self.device_info.loaded_models[model_name].shards
                return await self._process_model_shard(prompt, shard_info)
            else:
                # Handle full model inference
                return await self._process_full_model(prompt, model_name)
                
        except Exception as e:
            logger.error(f"Inference error on node {self.id}: {e}")
            raise