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
        try:
            import torch
            if torch.cuda.is_available():
                return [{
                    'name': torch.cuda.get_device_name(i),
                    'memory_total': torch.cuda.get_device_properties(i).total_memory / 1024**3,
                    'memory_used': (torch.cuda.get_device_properties(i).total_memory - 
                                  torch.cuda.memory_allocated(i)) / 1024**3
                } for i in range(torch.cuda.device_count())]
        except:
            pass
        
        try:
            # Try nvidia-smi as backup
            import subprocess
            result = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.used',
                                           '--format=csv,noheader,nounits']).decode()
            gpus = []
            for line in result.strip().split('\n'):
                name, total, used = line.split(',')
                gpus.append({
                    'name': name.strip(),
                    'memory_total': float(total)/1024,
                    'memory_used': float(used)/1024
                })
            return gpus
        except:
            return []
    
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
        self._ws = None
        self._heartbeat_task = None
        self._status_task = None
        self._message_handler_task = None
        
    async def _send_heartbeat(self):
        """Send periodic heartbeat to master"""
        while self.connected:
            try:
                if self._ws:
                    heartbeat = {
                        'type': 'heartbeat_response',
                        'id': self.node_name,
                        'timestamp': datetime.now().timestamp()
                    }
                    await self._ws.send(json.dumps(heartbeat))
                await asyncio.sleep(30)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                await asyncio.sleep(5)

    async def _status_update_loop(self):
        """Periodically send status updates"""
        while self.connected:
            try:
                if self._ws:
                    self.laptop_info.update()
                    system_info = self.laptop_info.to_dict()['system_info']
                    status = {
                        'type': 'status_update',
                        'id': self.node_name,
                        'device_info': {
                            'cpu_count': system_info['cpu_cores'],
                            'cpu_freq': system_info['cpu_freq']['current'] if system_info['cpu_freq'] else 0.0,
                            'total_memory': psutil.virtual_memory().total,
                            'available_memory': psutil.virtual_memory().available,
                            'gpu_count': len(system_info['gpu_info']),
                            'gpu_info': system_info['gpu_info'],
                            'hostname': socket.gethostname(),
                            'ip_address': socket.gethostbyname(socket.gethostname()),
                            'platform': system_info['platform'],
                            'role': 'laptop'
                        }
                    }
                    await self._ws.send(json.dumps(status))
                await asyncio.sleep(5)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error sending status update: {e}")
                await asyncio.sleep(5)

    async def _handle_master_messages(self):
        """Handle incoming messages from master"""
        while self.connected:
            try:
                if self._ws:
                    message = await self._ws.recv()
                    data = json.loads(message)
                    
                    if data.get('type') == 'heartbeat':
                        response = {
                            'type': 'heartbeat_response',
                            'id': self.node_name,
                            'timestamp': datetime.now().timestamp()
                        }
                        await self._ws.send(json.dumps(response))
                    elif data.get('type') == 'register_ack':
                        logger.info("Registration acknowledged by master")
                    else:
                        await self._handle_message(data)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("Master connection closed")
                break
            except Exception as e:
                logger.error(f"Error handling master message: {e}")
                await asyncio.sleep(1)

    async def start(self):
        """Start node operations with improved connection handling"""
        while True:
            try:
                async with websockets.connect(self.master_address) as websocket:
                    self._ws = websocket
                    self.connected = True
                    logger.info(f"Connected to master at {self.master_address}")
                    
                    # Format device info to match DeviceInfo structure
                    system_info = self.laptop_info.to_dict()['system_info']
                    registration = {
                        'type': 'register',
                        'id': self.node_name,
                        'device_info': {
                            'cpu_count': system_info['cpu_cores'],
                            'cpu_freq': system_info['cpu_freq']['current'] if system_info['cpu_freq'] else 0.0,
                            'total_memory': psutil.virtual_memory().total,
                            'available_memory': psutil.virtual_memory().available,
                            'gpu_count': len(system_info['gpu_info']),
                            'gpu_info': system_info['gpu_info'],
                            'hostname': socket.gethostname(),
                            'ip_address': socket.gethostbyname(socket.gethostname()),
                            'platform': system_info['platform'],
                            'role': 'laptop'
                        }
                    }
                    await websocket.send(json.dumps(registration))
                    logger.info(f"Registered with master as {self.node_name}")
                    
                    # Start background tasks
                    tasks = []
                    tasks.append(asyncio.create_task(self._send_heartbeat()))
                    tasks.append(asyncio.create_task(self._status_update_loop()))
                    tasks.append(asyncio.create_task(self._handle_master_messages()))
                    
                    # Wait for any task to complete (which likely means connection lost)
                    try:
                        await asyncio.gather(*tasks)
                    except Exception as e:
                        logger.error(f"Task error: {e}")
                    finally:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                                
            except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
                logger.warning(f"Connection failed: {e}. Retrying in {self.reconnect_delay}s...")
            except Exception as e:
                logger.error(f"Connection error: {e}")
            finally:
                self.connected = False
                self._ws = None
                await asyncio.sleep(self.reconnect_delay)

    async def _handle_message(self, data):
        """Handle incoming messages from master"""
        msg_type = data.get('type')
        if msg_type == 'topology':
            # Handle topology updates if needed
            pass
        elif msg_type == 'command':
            # Handle remote commands
            pass

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

@click.command()
@click.option('--master', required=True, help='Master node IP address')
@click.option('--port', default=8765, help='Master node port')
@click.option('--name', default=None, help='Custom name for this laptop node')
@async_command
async def start_laptop_node(master: str, port: int, name: str):
    """Start a laptop node to join the NeuroPack cluster"""
    master_url = f"ws://{master}:{port}"
    laptop_info = LaptopInfo(name)
    
    # Initial system info display
    system_info = laptop_info.to_dict()['system_info']
    logger.info("\n=== System Information ===")
    logger.info(f"Platform: {system_info['platform']} {system_info['platform_release']}")
    logger.info(f"CPU: {system_info['processor']}")
    logger.info(f"Cores: {system_info['cpu_cores']}")
    if system_info['cpu_freq']:
        logger.info(f"CPU Frequency: {system_info['cpu_freq']['current']/1000:.2f} GHz")
    logger.info("=======================")
    
    # Create node instance
    node = LaptopNode(
        master_address=master_url,
        node_name=name,
        laptop_info=laptop_info
    )
    
    try:
        # Create task group for concurrent operations
        async with asyncio.TaskGroup() as tg:
            # Resource update task
            tg.create_task(laptop_info.update_loop())
            # Node connection task
            tg.create_task(node.start())
            # Command interface task
            tg.create_task(handle_commands(node))
    except* KeyboardInterrupt:
        logger.info("\nShutting down laptop node...")
    except* Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    try:
        start_laptop_node()
    except KeyboardInterrupt:
        pass 