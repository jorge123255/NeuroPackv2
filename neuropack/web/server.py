import asyncio
import logging
import json
import websockets
from pathlib import Path
import sys
import multiprocessing
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import os

# Initialize logger
logger = logging.getLogger(__name__)

class TopologyServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.connections = set()
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
            self.connections.add(websocket)
            try:
                while True:
                    await websocket.receive_text()  # Keep connection alive
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.connections.remove(websocket)
                
    async def broadcast_topology(self, topology_data):
        """Broadcast topology updates to all connected clients"""
        logger.info(f"Broadcasting topology to {len(self.connections)} clients")
        logger.debug(f"Topology data: {topology_data}")
        
        dead_connections = set()
        for connection in self.connections:
            try:
                await connection.send_json(topology_data)
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                dead_connections.add(connection)
        
        # Cleanup dead connections
        self.connections -= dead_connections

    def run(self):
        """Run the web server"""
        logger.info(f"Starting web server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)

    def _get_default_html(self):
        """Return enhanced HTML template"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NeuroPack Cluster Topology</title>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #1a1a1a;
                    color: #ffffff;
                }
                #topology {
                    width: 100vw;
                    height: 100vh;
                }
                .node {
                    cursor: pointer;
                }
                .node circle {
                    fill: #4CAF50;
                    stroke: #fff;
                    stroke-width: 2px;
                    transition: all 0.3s ease;
                }
                .node.master circle {
                    fill: #ff4444;
                }
                .node:hover circle {
                    filter: brightness(1.2);
                }
                .link {
                    stroke: #666;
                    stroke-width: 2px;
                    stroke-opacity: 0.6;
                }
                .node text {
                    fill: white;
                    font-size: 12px;
                    text-anchor: middle;
                }
                .tooltip {
                    position: absolute;
                    padding: 10px;
                    background: rgba(0, 0, 0, 0.8);
                    color: white;
                    border-radius: 5px;
                    pointer-events: none;
                    font-size: 14px;
                    z-index: 1000;
                }
                #stats {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: rgba(0, 0, 0, 0.8);
                    padding: 15px;
                    border-radius: 5px;
                    min-width: 200px;
                }
                .stats-title {
                    font-size: 16px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .stats-item {
                    margin: 5px 0;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div id="topology"></div>
            <div id="stats">
                <div class="stats-title">Cluster Statistics</div>
                <div id="stats-content"></div>
            </div>
            <div class="tooltip" style="display: none;"></div>
            <script src="/static/js/topology.js"></script>
        </body>
        </html>
        """
        
if __name__ == "__main__":
    server = TopologyServer()
    server.run() 