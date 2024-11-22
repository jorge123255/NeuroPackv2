from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import logging
import asyncio
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class TopologyServer:
    def __init__(self, master_node):
        self.app = FastAPI()
        self.master_node = master_node
        self.connected_clients = set()
        
        # Mount static files
        static_dir = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Add routes
        @self.app.get("/")
        async def get_index():
            return HTMLResponse(self._get_index_html())
            
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_text()
                    # Handle the data
                    await websocket.send_text(f"Message received: {data}")
            except WebSocketDisconnect:
                pass

    def _get_index_html(self):
        """Return the index.html content"""
        html_path = Path(__file__).parent / "static" / "index.html"
        if html_path.exists():
            return html_path.read_text()
        else:
            return self._get_default_html()

    def _get_default_html(self):
        """Return default HTML if index.html doesn't exist"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NeuroPack Topology</title>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                body { margin: 0; background: #1a1a1a; color: #fff; font-family: Arial, sans-serif; }
                #topology { width: 100vw; height: 100vh; }
                .node { cursor: pointer; }
                .node text { fill: #fff; }
                .link { stroke: #666; stroke-width: 2px; }
                .master-node { fill: #4CAF50; }
                .laptop-node { fill: #2196F3; }
                .tooltip {
                    position: absolute;
                    padding: 10px;
                    background: rgba(0, 0, 0, 0.8);
                    border-radius: 5px;
                    color: white;
                    display: none;
                }
            </style>
        </head>
        <body>
            <div id="topology"></div>
            <div class="tooltip"></div>
            <script src="/static/js/topology.js"></script>
        </body>
        </html>
        """

    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connections"""
        await websocket.accept()
        self.connected_clients.add(websocket)
        try:
            while True:
                # Keep connection alive and handle any client messages
                data = await websocket.receive_json()
                await self._handle_client_message(websocket, data)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.connected_clients.remove(websocket)

    async def _handle_client_message(self, websocket: WebSocket, data: dict):
        """Handle messages from clients"""
        msg_type = data.get('type')
        if msg_type == 'get_topology':
            await self._send_topology(websocket)
        elif msg_type == 'node_action':
            await self._handle_node_action(data)

    async def _send_topology(self, websocket: WebSocket):
        """Send current topology to client"""
        topology_data = {
            'nodes': [],
            'links': []
        }

        # Add master node
        topology_data['nodes'].append({
            'id': 'master',
            'label': 'Master Node',
            'type': 'master',
            'gpu_count': len(self.master_node.get_gpu_info()),
            'status': 'active'
        })

        # Add connected nodes
        for name, node_data in self.master_node.nodes.items():
            node_info = node_data.get('node_info', {})
            resources = node_info.get('resources', {})
            system = node_info.get('system_info', {})

            topology_data['nodes'].append({
                'id': name,
                'label': name,
                'type': node_data.get('node_type', 'unknown'),
                'cpu_usage': resources.get('cpu_percent', 0),
                'memory_usage': resources.get('memory', {}).get('percent', 0),
                'gpu_info': system.get('gpu_info', []),
                'platform': system.get('platform', 'Unknown'),
                'status': 'connected'
            })

            # Add connection to master
            topology_data['links'].append({
                'source': 'master',
                'target': name,
                'value': 1,
                'status': 'active'
            })

        await websocket.send_json(topology_data)

    async def broadcast_topology(self):
        """Broadcast topology updates to all connected clients"""
        while True:
            if self.connected_clients:
                try:
                    for client in self.connected_clients:
                        await self._send_topology(client)
                except Exception as e:
                    logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(1)  # Update every second

    async def _handle_node_action(self, data: dict):
        """Handle node-related actions"""
        action = data.get('action')
        node_id = data.get('node_id')
        
        if action == 'disconnect':
            # Handle node disconnection
            if node_id in self.master_node.nodes:
                await self.master_node.disconnect_node(node_id)
        elif action == 'restart':
            # Handle node restart
            if node_id in self.master_node.nodes:
                await self.master_node.restart_node(node_id)

    def start(self):
        """Start the web server"""
        import uvicorn
        uvicorn.run(self.app, host="0.0.0.0", port=self.master_node.web_port) 