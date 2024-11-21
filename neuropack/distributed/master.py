import asyncio
import websockets
import json
import logging
from typing import Dict
import torch

logger = logging.getLogger(__name__)

class MasterNode:
    def __init__(self, port: int = 8765):
        self.port = port
        self.nodes: Dict[str, Dict] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        
        # Log GPU information
        if torch.cuda.is_available():
            logger.info(f"Found {torch.cuda.device_count()} GPUs:")
            for i in range(torch.cuda.device_count()):
                logger.info(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
        else:
            logger.warning("No GPUs found")
            
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
            
    async def process_message(self, websocket, data: Dict):
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
        """Start the master node"""
        async with websockets.serve(self.handle_connection, "0.0.0.0", self.port):
            logger.info(f"Master node running on port {self.port}")
            logger.info("Waiting for nodes to connect...")
            
            # Start periodic status updates
            while True:
                if self.nodes:
                    logger.info("\nCluster Status Update:")
                    logger.info(f"Connected nodes: {len(self.nodes)}")
                    for name, node_data in self.nodes.items():
                        resources = node_data.get('node_info', {}).get('resources', {})
                        logger.info(f"\nNode: {name}")
                        if resources:
                            logger.info(f"CPU Usage: {resources.get('cpu_percent')}%")
                            memory = resources.get('memory', {})
                            logger.info(f"Memory Used: {memory.get('percent')}%")
                            
                await asyncio.sleep(10)  # Update every 10 seconds