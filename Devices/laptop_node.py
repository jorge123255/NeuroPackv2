import asyncio
import click
import logging
from pathlib import Path
import sys

# Add NeuroPack root to Python path
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from neuropack.nodemanager.core.node import Node
except ImportError:
    # If the module structure doesn't exist, create a simple Node class
    class Node:
        def __init__(self, master_address: str, node_type: str = "laptop", node_name: str = None):
            self.master_address = master_address
            self.node_type = node_type
            self.node_name = node_name
            
        async def start(self):
            print(f"Starting {self.node_type} node: {self.node_name}")
            print(f"Connecting to master at: {self.master_address}")
            # Basic connection logic here

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--master', required=True, help='Master node IP address (e.g., 192.168.1.230)')
@click.option('--port', default=8765, help='Master node port')
@click.option('--name', required=True, help='Name for this laptop node')
def start_laptop_node(master: str, port: int, name: str):
    """Start a laptop node to join the NeuroPack cluster"""
    master_url = f"ws://{master}:{port}"
    
    logger.info(f"Starting laptop node, connecting to {master_url}")
    logger.info(f"Node name: {name}")
    
    node = Node(
        master_address=master_url,
        node_type="laptop",
        node_name=name
    )
    
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        logger.info("Shutting down laptop node...")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    start_laptop_node() 