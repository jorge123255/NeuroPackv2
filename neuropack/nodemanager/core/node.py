import asyncio
import websockets
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Node:
    def __init__(self, master_address: str, node_type: str = "laptop", 
                 node_name: str = None, node_info: dict = None):
        self.master_address = master_address
        self.node_type = node_type
        self.node_name = node_name
        self.node_info = node_info or {}
        
    async def start(self):
        """Start node operations"""
        logger.info(f"Starting {self.node_type} node: {self.node_name}")
        logger.info(f"Connecting to master at: {self.master_address}")
        
        while True:  # Add reconnection logic
            try:
                async with websockets.connect(self.master_address) as websocket:
                    await self._register(websocket)
                    await self._handle_messages(websocket)
            except websockets.ConnectionClosed:
                logger.warning("Connection lost. Attempting to reconnect in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(5)
                
    async def _register(self, websocket):
        """Register with master node"""
        registration_data = {
            'type': 'register',
            'data': {
                'node_type': self.node_type,
                'node_name': self.node_name,
                'node_info': self.node_info
            }
        }
        await websocket.send(json.dumps(registration_data))
        
    async def _handle_messages(self, websocket):
        """Handle incoming messages"""
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                await self._process_message(websocket, data)
            except websockets.ConnectionClosed:
                logger.info("Connection closed")
                break
                
    async def _process_message(self, websocket, data):
        """Process incoming messages"""
        msg_type = data.get('type')
        if msg_type == 'ping':
            await websocket.send(json.dumps({
                'type': 'pong',
                'data': {
                    'node_name': self.node_name,
                    'node_info': self.node_info
                }
            }))
        elif msg_type == 'cluster_info':
            nodes = data.get('data', {}).get('nodes', [])
            node_count = data.get('data', {}).get('node_count', 0)
            logger.info(f"\nCluster Status:")
            logger.info(f"Total nodes: {node_count}")
            logger.info(f"Connected nodes: {', '.join(nodes)}")
 