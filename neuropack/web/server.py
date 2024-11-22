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

class WebServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.setup_routes()
        
    def setup_routes(self):
        static_dir = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        @self.app.get("/")
        async def get_index():
            index_path = Path(__file__).parent / "static" / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return HTMLResponse(self._get_default_html())
            
    def _get_default_html(self):
        """Return default HTML if index.html doesn't exist"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>NeuroPack Topology</title>
            <script src="/static/js/d3.min.js"></script>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    font-family: Arial, sans-serif;
                    background: #1a1a1a;
                    color: #ffffff;
                }
                #topology {
                    width: 100vw;
                    height: 100vh;
                }
                .node {
                    fill: #4CAF50;
                    stroke: #fff;
                    stroke-width: 2px;
                }
                .link {
                    stroke: #999;
                    stroke-opacity: 0.6;
                }
                .node text {
                    fill: white;
                    font-size: 12px;
                }
                .tooltip {
                    position: absolute;
                    padding: 10px;
                    background: rgba(0, 0, 0, 0.8);
                    color: white;
                    border-radius: 5px;
                    pointer-events: none;
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
        
    def run(self):
        uvicorn.run(self.app, host=self.host, port=self.port)

if __name__ == "__main__":
    server = WebServer()
    server.run() 