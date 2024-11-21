import asyncio
import click
import logging
from pathlib import Path
import sys

# Add NeuroPack to Python path
repo_root = Path(__file__).parent.parent
sys.path.append(str(repo_root))

from neuropack.nodemanager.core.node import Node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--master', required=True, help='Master node IP address (e.g., 192.168.1.230)')
@click.option('--port', default=8765, help='Master node port')
@click.option('--name', default=None, help='Custom name for this laptop node')
async def start_laptop_node(master: str, port: int, name: str):
    """Start a laptop node to join the NeuroPack cluster"""
    master_url = f"ws://{master}:{port}"
    
    logger.info(f"Starting laptop node, connecting to {master_url}")
    if name:
        logger.info(f"Node name: {name}")
        
    node = Node(
        master_address=master_url,
        node_type="laptop",
        node_name=name
    )
    
    try:
        await node.start()
    except KeyboardInterrupt:
        logger.info("Shutting down laptop node...")
    except Exception as e:
        logger.error(f"Error: {e}")
        
def main():
    """Entry point for laptop node"""
    try:
        asyncio.run(start_laptop_node())
    except KeyboardInterrupt:
        logger.info("Laptop node stopped by user")

if __name__ == "__main__":
    main() 