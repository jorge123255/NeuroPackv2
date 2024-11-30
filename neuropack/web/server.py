import asyncio
import logging
import json
import websockets
from pathlib import Path
import sys
import multiprocessing
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import os
from typing import Set

# Initialize logger
logger = logging.getLogger(__name__)

class TopologyServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.connections: Set[WebSocket] = set()
        self.latest_topology = None
        self.setup_routes()
        
    def setup_routes(self):
        static_dir = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        @self.app.get("/")
        async def get_index():
            return HTMLResponse(self._get_default_html())
            
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            logger.info("New WebSocket client connected")
            self.connections.add(websocket)
            
            try:
                # Send initial topology if available
                if self.latest_topology:
                    await websocket.send_text(json.dumps(self.latest_topology))
                
                # Keep connection alive
                while True:
                    try:
                        data = await websocket.receive_text()
                        if data == "ping":
                            await websocket.send_text("pong")
                    except WebSocketDisconnect:
                        break
                    
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.connections.remove(websocket)
                logger.info(f"Client disconnected. Active connections: {len(self.connections)}")
                
    async def broadcast_topology(self, topology_data):
        """Broadcast topology updates to all connected clients"""
        if not self.connections:
            return
            
        logger.info(f"Broadcasting topology to {len(self.connections)} clients")
        
        # Convert string to dict if needed
        if isinstance(topology_data, str):
            try:
                topology_data = json.loads(topology_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON topology data: {e}")
                return
        
        self.latest_topology = topology_data
        
        dead_connections = set()
        for websocket in self.connections:
            try:
                # Send as JSON string
                await websocket.send_text(json.dumps(topology_data))
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                dead_connections.add(websocket)
        
        # Remove dead connections
        self.connections -= dead_connections

    async def broadcast_metrics(self, metrics_data):
        """Broadcast metrics updates to all connected clients"""
        logger.info(f"Broadcasting metrics to {len(self.connections)} clients")
        logger.debug(f"Metrics data: {metrics_data}")
        
        # Ensure metrics_data has the correct structure
        if not isinstance(metrics_data, dict) or 'nodes' not in metrics_data:
            logger.error("Invalid metrics data format")
            return
        
        topology_data = {
            'nodes': metrics_data['nodes'],
            'links': metrics_data['links'],
            'cluster_stats': metrics_data.get('cluster_stats', {})
        }
        
        await self.broadcast_topology(topology_data)

    async def start(self):
        """Start the web server asynchronously"""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    def _get_default_html(self):
        """Return enhanced HTML template"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NeuroPack LLM Cluster</title>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    font-family: 'Courier New', monospace;
                    background: #000000;
                    color: #33ff33;
                    overflow: hidden;
                }
                #topology {
                    width: 100vw;
                    height: 100vh;
                }
                .node-box {
                    fill: rgba(0, 0, 0, 0.7);
                    stroke: #33ff33;
                    stroke-width: 2px;
                }
                .link {
                    stroke: #33ff33;
                    stroke-width: 1px;
                    stroke-dasharray: 5,5;
                }
                .node text {
                    fill: #33ff33;
                    font-size: 12px;
                }
                #stats {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: rgba(0, 0, 0, 0.8);
                    border: 1px solid #33ff33;
                    padding: 15px;
                    font-family: 'Courier New', monospace;
                }
                .connection-status {
                    margin-bottom: 10px;
                    padding: 5px;
                    border-bottom: 1px solid #33ff33;
                }
                .gpu-meter {
                    margin: 5px 0;
                    height: 10px;
                    background: rgba(51, 255, 51, 0.2);
                    border: 1px solid #33ff33;
                }
                .gpu-meter-fill {
                    height: 100%;
                    background: #33ff33;
                    transition: width 0.3s ease;
                }
                .cluster-header {
                    position: fixed;
                    top: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    text-align: center;
                    font-size: 24px;
                    color: #33ff33;
                }
                .model-list {
                    position: fixed;
                    left: 20px;
                    top: 20px;
                    background: rgba(0, 0, 0, 0.8);
                    border: 1px solid #33ff33;
                    padding: 15px;
                }
            </style>
        </head>
        <body>
            <div class="cluster-header">
                <pre>
    _   __                    ____             __  
   / | / /___  __  ___________/ __ \\____ ______/ /__
  /  |/ / __ \\/ / / / ___/ __/ /_/ / __ `/ ___/ //_/
 / /|  / /_/ / /_/ / /  / /_/ ____/ /_/ / /__/ ,<   
/_/ |_/\\____/\\__,_/_/   \\__/_/    \\__,_/\\___/_/|_|  
                </pre>
                <div>Distributed LLM Cluster</div>
            </div>
            <div id="topology"></div>
            <div id="stats">
                <div class="connection-status"></div>
                <div class="stats-title">Cluster Statistics</div>
                <div id="stats-content"></div>
            </div>
            <div class="model-list">
                <div class="title">Available Models</div>
                <div id="model-content"></div>
            </div>
            <script src="/static/js/topology.js"></script>
        </body>
        </html>
        """
        
if __name__ == "__main__":
    server = TopologyServer()
    asyncio.run(server.start()) 