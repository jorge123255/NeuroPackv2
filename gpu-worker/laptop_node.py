import asyncio
import click
import logging
import psutil
import platform
import json
import uuid
from datetime import datetime
from pathlib import Path
import sys
from functools import wraps
import aioconsole
import websockets
import socket
import os

# Add NeuroPack root to Python path
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from neuropack.nodemanager.core.node import Node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper for async click commands
def async_command(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

class LaptopInfo:
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.node_id = str(uuid.uuid4())
        self.update()
        
    def update(self):
        """Update system information"""
        self.cpu_percent = psutil.cpu_percent(interval=1)
        self.memory = psutil.virtual_memory()
        self.disk = psutil.disk_usage('/')
        self.network = psutil.net_io_counters()
        self.timestamp = datetime.now().isoformat()
        
    def get_gpu_info(self):
        """Get GPU information"""
        gpus = []
        
        # Try PyTorch first
        try:
            import torch
            logger.info("Checking GPU via PyTorch...")
            if torch.cuda.is_available():
                logger.info(f"Found {torch.cuda.device_count()} CUDA devices")
                for i in range(torch.cuda.device_count()):
                    gpu_info = {
                        'name': torch.cuda.get_device_name(i),
                        'memory_total': torch.cuda.get_device_properties(i).total_memory / 1024**3,
                        'memory_used': torch.cuda.memory_allocated(i) / 1024**3,
                        'memory_free': (torch.cuda.get_device_properties(i).total_memory - 
                                      torch.cuda.memory_allocated(i)) / 1024**3
                    }
                    gpus.append(gpu_info)
                    logger.info(f"GPU {i}: {gpu_info}")
            else:
                logger.info("No CUDA devices available via PyTorch")
        except Exception as e:
            logger.warning(f"Error getting GPU info via PyTorch: {str(e)}")
        
        # Try nvidia-smi if PyTorch didn't find anything
        if not gpus:
            try:
                logger.info("Checking GPU via nvidia-smi...")
                import subprocess
                result = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free',
                                               '--format=csv,noheader,nounits']).decode()
                for line in result.strip().split('\n'):
                    name, total, used, free = line.split(',')
                    gpu_info = {
                        'name': name.strip(),
                        'memory_total': float(total)/1024,
                        'memory_used': float(used)/1024,
                        'memory_free': float(free)/1024
                    }
                    gpus.append(gpu_info)
                    logger.info(f"Found GPU via nvidia-smi: {gpu_info}")
            except Exception as e:
                logger.warning(f"Error getting GPU info via nvidia-smi: {str(e)}")
        
        return gpus
    
    def to_dict(self):
        return {
            'node_name': self.node_name,
            'node_id': self.node_id,
            'system_info': {
                'platform': platform.system(),
                'platform_release': platform.release(),
                'processor': platform.processor(),
                'cpu_cores': psutil.cpu_count(),
                'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                'gpu_info': self.get_gpu_info()
            },
            'resources': {
                'cpu_percent': self.cpu_percent,
                'memory': {
                    'total': self.memory.total,
                    'available': self.memory.available,
                    'percent': self.memory.percent
                },
                'disk': {
                    'total': self.disk.total,
                    'used': self.disk.used,
                    'free': self.disk.free,
                    'percent': self.disk.percent
                },
                'network': {
                    'bytes_sent': self.network.bytes_sent,
                    'bytes_recv': self.network.bytes_recv
                }
            },
            'timestamp': self.timestamp
        }

    async def update_loop(self):
        """Continuously update system information"""
        while True:
            self.update()
            await asyncio.sleep(5)

class LaptopNode(Node):
    """Extended Node class with laptop-specific features"""
    def __init__(self, master_address: str, node_name: str, laptop_info: 'LaptopInfo'):
        super().__init__(master_address, "laptop", node_name)
        self.laptop_info = laptop_info
        self.connected = False
        self.reconnect_delay = 5
        
    async def start(self):
        while True:
            try:
                master_url = f"ws://{os.getenv('MASTER_HOST')}:{os.getenv('MASTER_PORT')}"
                logger.info(f"Attempting to connect to master at {master_url}")
                
                async with websockets.connect(master_url) as websocket:
                    logger.info("Connected to master node")
                    await self.register(websocket)
                    await self.message_loop(websocket)
                    
            except (ConnectionRefusedError, OSError) as e:
                logger.error(f"Connection failed: {e}")
                await asyncio.sleep(5)  # Wait 5 seconds before retry
                
    async def register(self, websocket):
        system_info = self.laptop_info.to_dict()['system_info']
        registration = {
            'type': 'register',
            'id': os.getenv('NODE_ID'),
            'role': os.getenv('NODE_ROLE'),
            'device_info': {
                'cpu_count': system_info['cpu_cores'],
                'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                'total_memory': psutil.virtual_memory().total,
                'available_memory': psutil.virtual_memory().available,
                'gpu_count': len(system_info['gpu_info']),
                'hostname': socket.gethostname(),
                'ip_address': socket.gethostbyname(socket.gethostname()),
                'platform': platform.system(),
                'gpu_info': [{
                    'name': gpu['name'],
                    'total_memory': float(gpu['memory_total']),
                    'current_memory': float(gpu['memory_used']),
                    'free_memory': float(gpu['memory_free']),
                    'utilization': 0,
                    'temperature': 0,
                    'power_draw': 0
                } for gpu in system_info['gpu_info']]
            }
        }
        await websocket.send(json.dumps(registration))

async def handle_commands(node: LaptopNode):
    """Async command handler"""
    while True:
        try:
            command = await aioconsole.ainput("\nCommands:\n"
                                            "  status - Show node status\n"
                                            "  quit   - Exit node\n"
                                            "> ")
            
            if command.lower() == 'quit':
                logger.info("Shutting down...")
                return True
            elif command.lower() == 'status':
                await node.show_status()
            else:
                logger.info("Unknown command. Available commands: status, quit")
        except Exception as e:
            logger.error(f"Command error: {e}")
    return False

async def handle_message(data):
    # Handle other message types
    pass

@click.command()
@click.option('--master', required=True, help='Master node IP address')
@click.option('--port', default=8765, help='Master node port')
@click.option('--name', default=None, help='Custom name for this laptop node')
@async_command
async def start_laptop_node(master: str, port: int, name: str):
    """Start a laptop node to join the NeuroPack cluster"""
    master_url = f"ws://{master}:{port}"
    laptop_info = LaptopInfo(name)
    
    while True:
        try:
            async with websockets.connect(master_url, ping_interval=20, ping_timeout=20) as websocket:
                logger.info(f"Connected to master at {master_url}")
                system_info = laptop_info.to_dict()['system_info']
                
                # Format device info to match DeviceInfo requirements
                device_info = {
                    'cpu_count': system_info['cpu_cores'],
                    'cpu_freq': system_info['cpu_freq']['current'] if system_info['cpu_freq'] else 0.0,
                    'total_memory': psutil.virtual_memory().total / (1024 * 1024 * 1024),  # Convert to GB
                    'available_memory': psutil.virtual_memory().available / (1024 * 1024 * 1024),  # Convert to GB
                    'gpu_count': len(system_info['gpu_info']),
                    'gpu_info': [{
                        'name': gpu['name'],
                        'total_memory': float(gpu['memory_total']),
                        'current_memory': float(gpu['memory_used']),
                        'free_memory': float(gpu['memory_free']),
                        'utilization': 0,
                        'temperature': 0,
                        'power_draw': 0
                    } for gpu in system_info['gpu_info']],
                    'hostname': socket.gethostname(),
                    'ip_address': socket.gethostbyname(socket.gethostname()),
                    'platform': platform.system(),
                    'role': 'gpu-worker',  # Add role for frontend
                    'status': 'active'     # Add status for frontend
                }
                
                await websocket.send(json.dumps({
                    'type': 'register',
                    'id': os.getenv('NODE_ID', name or str(uuid.uuid4())),
                    'role': 'gpu-worker',
                    'device_info': device_info
                }))
                
                while True:
                    try:
                        msg = await websocket.recv()
                        data = json.loads(msg)
                        
                        if data.get('type') == 'heartbeat':
                            # Respond to heartbeat
                            await websocket.send(json.dumps({
                                'type': 'heartbeat_response',
                                'id': os.getenv('NODE_ID', name or str(uuid.uuid4())),
                                'device_info': device_info
                            }))
                        else:
                            # Handle other message types
                            await handle_message(data)
                            
                    except websockets.ConnectionClosed:
                        logger.warning("Connection closed by server")
                        break
                    except json.JSONDecodeError:
                        logger.error("Invalid message format")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        
        except (ConnectionRefusedError, OSError) as e:
            logger.error(f"Connection failed: {e}")
            await asyncio.sleep(5)  # Wait before retrying
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await asyncio.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    try:
        start_laptop_node()
    except KeyboardInterrupt:
        pass