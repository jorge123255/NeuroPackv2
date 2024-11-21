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
        """Start node operations with reconnection handling"""
        while True:
            try:
                async with websockets.connect(self.master_address) as websocket:
                    self.connected = True
                    logger.info(f"Connected to master at {self.master_address}")
                    
                    # Start status update loop
                    update_task = asyncio.create_task(self._status_update_loop(websocket))
                    
                    try:
                        await asyncio.gather(
                            self._register(websocket),
                            self._handle_messages(websocket)
                        )
                    finally:
                        update_task.cancel()
                        
            except websockets.ConnectionClosed:
                self.connected = False
                logger.warning("Connection closed. Attempting to reconnect...")
                await asyncio.sleep(self.reconnect_delay)
            except Exception as e:
                self.connected = False
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(self.reconnect_delay)
    
    async def _status_update_loop(self, websocket):
        """Periodically send status updates to master"""
        while True:
            try:
                status_update = {
                    'type': 'status_update',
                    'data': {
                        'node_type': self.node_type,
                        'node_name': self.node_name,
                        'node_info': self.laptop_info.to_dict()
                    }
                }
                await websocket.send(json.dumps(status_update))
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Error sending status update: {e}")
                await asyncio.sleep(5)

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