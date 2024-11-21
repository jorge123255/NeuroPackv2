import asyncio
import logging
import json
import websockets
from pathlib import Path
import sys
from datetime import datetime
from typing import Dict, List, Optional
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.tree import Tree

# Fix import paths
from ..distributed.node import Node, DeviceInfo
from ..web.server import TopologyServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MasterNode:
    def __init__(self, port: int = 8765, web_port: int = 8080):
        self.port = port
        self.nodes: Dict[str, Dict] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.start_time = datetime.now()
        self.console = Console()
        self.web_port = web_port
        self.web_server = TopologyServer(self)
        self.layout = self.create_topology_display()
        self.live = Live(self.layout, refresh_per_second=4)
        
        # Log GPU information
        if torch.cuda.is_available():
            logger.info(f"Found {torch.cuda.device_count()} GPUs:")
            for i in range(torch.cuda.device_count()):
                logger.info(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
        else:
            logger.warning("No GPUs found")
            
    def create_topology_display(self) -> Layout:
        """Create rich layout for topology display"""
        layout = Layout()
        layout.split_column(
            Layout(name="header"),
            Layout(name="main"),
            Layout(name="footer")
        )
        
        # Header with cluster info
        header = Table.grid()
        header.add_row(
            f"[bold green]NeuroPack Master Node[/] - Running since {self.start_time.strftime('%H:%M:%S')}"
        )
        header.add_row(f"Connected Nodes: {len(self.nodes)}")
        
        # Main topology tree
        tree = Tree("🖥️ [bold yellow]Master Node[/]")
        
        for name, node_data in self.nodes.items():
            node_info = node_data.get('node_info', {})
            resources = node_info.get('resources', {})
            system = node_info.get('system_info', {})
            
            # Create node branch
            node_tree = tree.add(
                f"📱 [bold blue]{name}[/] ({system.get('platform', 'Unknown')})"
            )
            
            # Add resource info
            if resources:
                cpu = resources.get('cpu_percent', 0)
                mem = resources.get('memory', {}).get('percent', 0)
                node_tree.add(f"CPU: {cpu}% | RAM: {mem}%")
                
                # Add GPU info if available
                if system.get('gpu_info'):
                    for gpu in system.get('gpu_info', []):
                        node_tree.add(f"🎮 GPU: {gpu['name']} ({gpu['memory_used']}GB/{gpu['memory_total']}GB)")
        
        # Footer with stats
        footer = Table.grid()
        footer.add_row("Press Ctrl+C to exit")
        
        # Update layout
        layout["header"].update(Panel(header))
        layout["main"].update(Panel(tree))
        layout["footer"].update(Panel(footer))
        
        return layout
        
    async def handle_connection(self, websocket):
        """Handle incoming WebSocket connections"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(websocket, data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except websockets.ConnectionClosed:
            await self.handle_disconnection(websocket)
            
    async def process_message(self, websocket, data: dict):
        """Process incoming messages"""
        try:
            msg_type = data.get('type')
            if msg_type == 'register':
                await self.register_node(websocket, data['data'])
            elif msg_type == 'status_update':
                node_data = data.get('data', {})
                node_name = node_data.get('node_name')
                if node_name in self.nodes:
                    self.nodes[node_name].update(node_data)
                    resources = node_data.get('node_info', {}).get('resources', {})
                    if resources:
                        logger.info(f"\nStatus update from {node_name}:")
                        logger.info(f"CPU Usage: {resources.get('cpu_percent')}%")
                        memory = resources.get('memory', {})
                        logger.info(f"Memory Used: {memory.get('percent')}%")
                        disk = resources.get('disk', {})
                        logger.info(f"Disk Used: {disk.get('percent')}%")
            elif msg_type == 'pong':
                logger.debug(f"Received pong from {data.get('data', {}).get('node_name')}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
    async def register_node(self, websocket, node_data: Dict):
        """Register a new node"""
        try:
            node_name = node_data.get('node_name')
            node_type = node_data.get('node_type')
            node_info = node_data.get('node_info', {})
            
            if not node_name:
                logger.error("Node name missing in registration data")
                return
                
            self.nodes[node_name] = node_data
            self.connections[node_name] = websocket
            
            logger.info(f"\nNew {node_type} node registered: {node_name}")
            logger.info(f"System: {node_info.get('system_info', {}).get('platform')} "
                       f"{node_info.get('system_info', {}).get('platform_release')}")
            
            resources = node_info.get('resources', {})
            if resources:
                memory = resources.get('memory', {})
                logger.info(f"Memory: {memory.get('total', 0)/1024/1024/1024:.1f}GB total, "
                          f"{memory.get('percent', 0)}% used")
                logger.info(f"CPU Usage: {resources.get('cpu_percent', 0)}%")
                
            logger.info(f"Total nodes connected: {len(self.nodes)}")
            await self.broadcast_cluster_info()
        except Exception as e:
            logger.error(f"Error in register_node: {e}")
        
    async def handle_disconnection(self, websocket):
        """Handle node disconnection"""
        try:
            disconnected = [name for name, conn in self.connections.items() if conn == websocket]
            for node_name in disconnected:
                del self.nodes[node_name]
                del self.connections[node_name]
                logger.info(f"Node disconnected: {node_name}")
            logger.info(f"Total nodes connected: {len(self.nodes)}")
        except Exception as e:
            logger.error(f"Error in handle_disconnection: {e}")
            
    async def broadcast_cluster_info(self):
        """Broadcast cluster information to all nodes"""
        cluster_info = {
            'type': 'cluster_info',
            'data': {
                'node_count': len(self.nodes),
                'nodes': list(self.nodes.keys())
            }
        }
        for conn in self.connections.values():
            try:
                await conn.send(json.dumps(cluster_info))
            except Exception as e:
                logger.error(f"Error broadcasting to node: {e}")
                
    async def start(self):
        """Start the master node and web interface"""
        # Start web server in separate process
        web_process = multiprocessing.Process(
            target=uvicorn.run,
            args=(self.web_server.app,),
            kwargs={
                "host": "0.0.0.0",
                "port": self.web_port,
                "log_level": "info"
            }
        )
        web_process.start()
        
        # Start WebSocket server for nodes
        async with websockets.serve(self.handle_connection, "0.0.0.0", self.port):
            logger.info(f"Master node running on port {self.port}")
            logger.info(f"Web interface available at http://localhost:{self.web_port}")
            
            # Start topology broadcast
            await self.web_server.broadcast_topology()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--web-port', type=int, default=8080)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    args = parser.parse_args()

    master = MasterNode(port=args.port, web_port=args.web_port)
    
    # Start both services
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(master.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        loop.close()

if __name__ == "__main__":
    main()