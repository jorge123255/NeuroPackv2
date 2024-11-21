from typing import Dict, Optional
import asyncio
import websockets
import json
import logging
from pathlib import Path
import torch
from NeuroPack.neuropack.distributed.node import Node, DeviceInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MasterNode(Node):
    def __init__(self, port: int = 8765):
        super().__init__(master_address=None)  # This is the master
        self.port = port
        self.nodes: Dict[str, Dict] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        
    async def handle_connection(self, websocket, path):
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_message(websocket, data)
                
        except websockets.ConnectionClosed:
            await self.handle_disconnection(websocket)
            
    async def process_message(self, websocket, data: Dict):
        msg_type = data.get('type')
        if msg_type == 'register':
            await self.register_node(websocket, data['data'])
        elif msg_type == 'task_request':
            await self.handle_task_request(websocket, data['data'])
            
    async def register_node(self, websocket, node_data: Dict):
        node_id = node_data['id']
        self.nodes[node_id] = node_data['device_info']
        self.connections[node_id] = websocket
        logger.info(f"New node registered: {node_id}")
        await self.broadcast_cluster_info()
        
    async def start(self):
        async with websockets.serve(self.handle_connection, "0.0.0.0", self.port):
            logger.info(f"Master node running on port {self.port}")
            logger.info(f"GPU Configuration: {torch.cuda.device_count()} GPUs available")
            await asyncio.Future()  # run forever 