import asyncio
import json
import logging
import websockets
from pathlib import Path
import sys
from typing import Dict, Set, Optional
from task_manager import TaskManager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup FastAPI app
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/web/static", StaticFiles(directory="web/static"), name="web_static")

# Setup templates
templates = Jinja2Templates(directory="web/templates")

# Response model for health check
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    nodes: int
    tasks: dict

class MasterNode:
    def __init__(self, host: str = '0.0.0.0', websocket_port: int = 8765, web_port: int = 8080):
        self.host = host
        self.websocket_port = websocket_port
        self.web_port = web_port
        self.task_manager = TaskManager()
        self.connected_nodes: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.node_types: Dict[str, str] = {}  # Maps node_id to node_type
        
    async def start_websocket_server(self):
        """Start the WebSocket server"""
        server = await websockets.serve(
            self.handle_connection,
            self.host, 
            self.websocket_port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.websocket_port}")
        await asyncio.Future()  # run forever

    def start_web_server(self):
        """Start the FastAPI web server"""
        config = uvicorn.Config(app, host=self.host, port=self.web_port, log_level="info")
        server = uvicorn.Server(config)
        return server.serve()
            
    async def handle_connection(self, websocket):
        """Handle new node connections"""
        node_id = None
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if node_id is None:
                    # Handle initial registration
                    if data.get('type') == 'register':
                        node_id = data.get('id')
                        node_type = data.get('node_type')
                        
                        if node_id and node_type:
                            self.connected_nodes[node_id] = websocket
                            self.node_types[node_id] = node_type
                            
                            if node_type == 'laptop':
                                # Register node resources
                                device_info = data.get('device_info', {})
                                self.task_manager.register_node(node_id, device_info)
                            
                            logger.info(f"Registered {node_type} node: {node_id}")
                            
                            # Send initial topology
                            await self.broadcast_topology()
                    continue
                
                # Handle other message types
                msg_type = data.get('type')
                
                if msg_type == 'status_update':
                    if self.node_types.get(node_id) == 'laptop':
                        self.task_manager.update_node_status(node_id, data.get('device_info', {}))
                        await self.broadcast_topology()
                        
                elif msg_type == 'task_result':
                    await self.task_manager.handle_task_result(node_id, data)
                    await self.broadcast_topology()
                    
                elif msg_type == 'chat':
                    # Handle chat messages from web clients
                    if self.node_types.get(node_id) == 'client':
                        task_id = await self.task_manager.create_task(
                            task_type='CHAT',
                            data={
                                'model': data.get('model', 'llama2'),
                                'message': data.get('message', ''),
                                'client_id': node_id
                            }
                        )
                        logger.info(f"Created chat task {task_id} for client {node_id}")
                    
                elif msg_type == 'error':
                    logger.error(f"Error from node {node_id}: {data.get('message')}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for node {node_id}")
        finally:
            if node_id:
                await self.handle_node_disconnect(node_id)
                
    async def handle_node_disconnect(self, node_id: str):
        """Handle node disconnection"""
        if node_id in self.connected_nodes:
            del self.connected_nodes[node_id]
            
        if node_id in self.node_types:
            node_type = self.node_types[node_id]
            del self.node_types[node_id]
            
            if node_type == 'laptop':
                self.task_manager.remove_node(node_id)
                
        await self.broadcast_topology()
        logger.info(f"Node {node_id} disconnected")
        
    async def broadcast_topology(self):
        """Broadcast topology updates to all nodes"""
        topology = {
            'type': 'topology',
            'nodes': [
                {'id': node_id, 'type': node_type}
                for node_id, node_type in self.node_types.items()
            ],
            'stats': self.task_manager.get_cluster_status()
        }
        
        await self.broadcast_message(topology)
        
    async def broadcast_message(self, message: Dict):
        """Broadcast a message to all connected nodes"""
        if not self.connected_nodes:
            return
            
        message_str = json.dumps(message)
        await asyncio.gather(
            *[
                node.send(message_str)
                for node in self.connected_nodes.values()
            ],
            return_exceptions=True
        )
        
    async def assign_task(self, task: Dict):
        """Assign a task to the best available node"""
        memory_required = task.get('data', {}).get('memory_required', 0)
        best_node = self.task_manager.get_best_node(memory_required)
        
        if best_node and best_node in self.connected_nodes:
            try:
                await self.connected_nodes[best_node].send(json.dumps(task))
                logger.info(f"Assigned task {task['task_id']} to node {best_node}")
                return True
            except Exception as e:
                logger.error(f"Error assigning task to node {best_node}: {e}")
                
        return False
        
    async def process_task_queue(self):
        """Process tasks in the queue"""
        while True:
            try:
                task = await self.task_manager.task_queue.get()
                success = await self.assign_task(task)
                
                if not success:
                    # Put task back in queue if assignment failed
                    await self.task_manager.task_queue.put(task)
                    await asyncio.sleep(1)  # Wait before retrying
                    
            except Exception as e:
                logger.error(f"Error processing task queue: {e}")
                await asyncio.sleep(1)
                
# Create a global master node instance
master_node = MasterNode()

@app.get("/")
async def root(request: Request):
    """Serve the topology visualization"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "cluster_status": {
                "nodes": len(master_node.connected_nodes),
                "node_types": master_node.node_types,
                "tasks": master_node.task_manager.get_cluster_status()
            }
        }
    )

@app.get("/chat")
async def chat(request: Request):
    """Serve the chat interface"""
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "ws_url": f"ws://{request.client.host}:{master_node.websocket_port}/ws"
        }
    )

@app.get("/api/topology")
async def get_topology():
    """Get current cluster topology"""
    return {
        "nodes": [
            {
                "id": node_id,
                "type": node_type,
                "status": "connected"
            }
            for node_id, node_type in master_node.node_types.items()
        ],
        "stats": master_node.task_manager.get_cluster_status()
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Docker"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        nodes=len(master_node.connected_nodes),
        tasks=master_node.task_manager.get_cluster_status()
    )

async def main():
    # Start task queue processor
    asyncio.create_task(master_node.process_task_queue())
    
    # Create tasks for both servers
    websocket_server = asyncio.create_task(master_node.start_websocket_server())
    web_server = asyncio.create_task(master_node.start_web_server())
    
    # Wait for both servers
    await asyncio.gather(websocket_server, web_server)
    
if __name__ == "__main__":
    asyncio.run(main())
