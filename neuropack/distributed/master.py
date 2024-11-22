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
        self.web_server = TopologyServer(host=host, port=web_port)
        self.web_process = None
        
    async def start(self):
        """Start the master node and web interface"""
        logger.info(f"Starting master node on {self.host}:{self.port}")
        
        # Add self to nodes
        self.nodes[self.id] = self.device_info
        
        # Start web interface in separate process
        self.web_process = multiprocessing.Process(
            target=self.web_server.run
        )
        self.web_process.start()
        
        # Initial topology broadcast
        await self.broadcast_topology()
        
        # Start WebSocket server
        async with websockets.serve(self.handle_connection, self.host, self.port):
            await asyncio.Future()  # run forever
            
    async def handle_connection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming WebSocket connections"""
        node_id = None
        try:
            # Wait for initial registration message
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
                
                # Handle messages from this node
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.handle_message(node_id, data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid message from node {node_id}")
                        
        except websockets.ConnectionClosed:
            logger.info(f"Node {node_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling connection: {e}", exc_info=True)
        finally:
            # Cleanup on disconnect
            if node_id:
                if node_id in self.connections:
                    del self.connections[node_id]
                if node_id in self.nodes:
                    del self.nodes[node_id]
                await self.broadcast_topology()
            
    async def handle_message(self, node_id: str, data: dict):
        """Handle incoming messages from nodes"""
        try:
            msg_type = data.get('type')
            
            if msg_type == 'status_update':
                # Update node status
                if 'device_info' in data:
                    device_info = DeviceInfo(**data['device_info'])
                    self.nodes[node_id] = device_info
                    await self.broadcast_topology()
                    
        except Exception as e:
            logger.error(f"Error handling message from {node_id}: {e}")
            
    async def broadcast_topology(self):
        """Broadcast current topology to web interface"""
        try:
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
            logger.debug(f"Topology data: {topology}")
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