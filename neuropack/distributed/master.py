import asyncio
import json
import logging
import multiprocessing
from typing import Dict, Set
import websockets
from dataclasses import asdict
from neuropack.web.server import TopologyServer
from neuropack.distributed.node import Node, DeviceInfo

logger = logging.getLogger(__name__)

class MasterNode(Node):
    def __init__(self, host="0.0.0.0", port=8765, web_port=8080):
        super().__init__(master_host=host, master_port=port)
        self.host = host
        self.port = port
        self.web_port = web_port
        self.is_master = True
        self.nodes: Dict[str, DeviceInfo] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.web_server = None
        
    async def start(self):
        """Start the master node and web interface"""
        logger.info(f"Starting master node on {self.host}:{self.port}")
        
        # Add self to nodes with master info
        self.nodes[self.id] = self.device_info
        
        # Create web server in the same event loop
        self.web_server = TopologyServer(host=self.host, port=self.web_port)
        
        # Start both servers concurrently
        await asyncio.gather(
            self.web_server.start(),
            websockets.serve(self.handle_connection, self.host, self.port)
        )
        
    async def handle_connection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming WebSocket connections"""
        node_id = None
        try:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get('type') == 'register':
                node_id = data['id']
                device_info = DeviceInfo(**data['device_info'])
                
                # Store connection and device info
                self.connections[node_id] = websocket
                self.nodes[node_id] = device_info
                
                logger.info(f"Node {node_id} connected")
                await self.broadcast_topology()
                
                try:
                    async for message in websocket:
                        await self.handle_message(node_id, message)
                except websockets.ConnectionClosed:
                    logger.info(f"Node {node_id} disconnected")
                finally:
                    if node_id in self.connections:
                        del self.connections[node_id]
                    if node_id in self.nodes:
                        del self.nodes[node_id]
                    await self.broadcast_topology()
                    
        except Exception as e:
            logger.error(f"Error handling connection: {e}", exc_info=True)
            if node_id:
                if node_id in self.connections:
                    del self.connections[node_id]
                if node_id in self.nodes:
                    del self.nodes[node_id]
                await self.broadcast_topology()

    async def handle_message(self, node_id: str, message: str):
        """Handle incoming messages from nodes"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'status_update':
                # Update node status
                if 'device_info' in data:
                    self.nodes[node_id] = DeviceInfo(**data['device_info'])
                    await self.broadcast_topology()
            elif msg_type == 'model_update':
                # Handle model updates
                if 'models' in data:
                    if node_id in self.nodes:
                        self.nodes[node_id].loaded_models = data['models']
                        await self.broadcast_topology()
                        
        except Exception as e:
            logger.error(f"Error handling message from {node_id}: {e}")

    async def broadcast_topology(self):
        """Broadcast current topology to web interface"""
        try:
            # Create topology data
            topology = {
                'nodes': [
                    {
                        'id': node_id,
                        'info': asdict(info),
                        'role': 'master' if node_id == self.id else 'worker'
                    }
                    for node_id, info in self.nodes.items()
                ],
                'links': [
                    {
                        'source': self.id,
                        'target': node_id
                    }
                    for node_id in self.nodes.keys() if node_id != self.id
                ]
            }
            
            logger.info(f"Broadcasting topology: {len(self.nodes)} nodes")
            if self.web_server:
                await self.web_server.broadcast_topology(topology)
            
            # Also broadcast to connected nodes
            message = json.dumps({'type': 'topology', 'data': topology})
            for connection in self.connections.values():
                try:
                    await connection.send(message)
                except Exception as e:
                    logger.error(f"Failed to send topology to node: {e}")
            
        except Exception as e:
            logger.error(f"Error broadcasting topology: {e}", exc_info=True)

    async def shutdown(self):
        """Shutdown the master node"""
        logger.info("Shutting down master node...")
        # Close all connections
        for connection in self.connections.values():
            await connection.close()
        # Clear node data
        self.connections.clear()
        self.nodes.clear()

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