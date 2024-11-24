import asyncio
import logging
import json
import websockets
from pathlib import Path
import sys
import multiprocessing
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from starlette.websockets import WebSocketState
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import os
from typing import Set
import uuid

# Add the parent directory to the Python path so we can import from web package
sys.path.append(str(Path(__file__).parent.parent))
from web.websocket import ConnectionManager

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TopologyServer:
    def __init__(self, host: str = '0.0.0.0', websocket_port: int = 8765, web_port: int = 8080):
        self.host = host
        self.websocket_port = websocket_port
        self.web_port = web_port
        self.app = FastAPI(title="NeuroPack Topology Server")
        self.connection_manager = ConnectionManager()
        self.latest_topology = None
        
        # Configure CORS with explicit WebSocket support
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
        
        self.setup_routes()
        logger.info("TopologyServer initialized")
        
    def setup_routes(self):
        try:
            # Set up the static and templates directories
            static_dir = Path(__file__).parent.parent / "static"
            templates_dir = Path(__file__).parent / "templates"
            logger.info(f"Static directory: {static_dir} (exists: {static_dir.exists()})")
            logger.info(f"Templates directory: {templates_dir} (exists: {templates_dir.exists()})")
            
            if not static_dir.exists():
                logger.error(f"Static directory does not exist: {static_dir}")
                static_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created static directory: {static_dir}")

            # Initialize Jinja2 templates
            templates = Jinja2Templates(directory=str(templates_dir))
            
            # Mount static files
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            
            @self.app.get("/", response_class=HTMLResponse)
            async def get_index(request: Request):
                return templates.TemplateResponse("index.html", {"request": request})
            
            @self.app.get("/health")
            async def health_check():
                return {"status": "healthy"}
            
            @self.app.get("/chat", response_class=HTMLResponse)
            async def get_chat(request: Request):
                return templates.TemplateResponse("chat.html", {"request": request})
            
            @self.app.websocket("/ws")
            async def websocket_endpoint(websocket: WebSocket):
                logger.info(f"New WebSocket connection attempt from {websocket.client.host}")
                try:
                    await websocket.accept()
                    logger.info(f"WebSocket connection accepted for {websocket.client.host}")
                    
                    await self.connection_manager.connect(websocket)
                    logger.info(f"Client {websocket.client.host} added to connection manager")
                    
                    if self.latest_topology is not None:
                        await websocket.send_json(self.latest_topology)
                        logger.info(f"Sent initial topology to {websocket.client.host}")
                    
                    try:
                        while True:
                            data = await websocket.receive_text()
                            logger.debug(f"Received message from {websocket.client.host}: {data}")
                    except WebSocketDisconnect:
                        logger.info(f"WebSocket disconnected for {websocket.client.host}")
                    except Exception as e:
                        logger.error(f"Error receiving message: {e}", exc_info=True)
                    finally:
                        await self.connection_manager.disconnect(websocket)
                        logger.info(f"Client {websocket.client.host} removed from connection manager")
                        
                except Exception as e:
                    logger.error(f"Error in websocket_endpoint: {e}", exc_info=True)
            
            logger.info("Routes configured successfully")
        except Exception as e:
            logger.error(f"Error setting up routes: {e}", exc_info=True)
            raise

    async def broadcast_topology(self, topology_data: dict):
        """Broadcast topology data to all connected WebSocket clients"""
        self.latest_topology = topology_data
        await self.connection_manager.broadcast(json.dumps(topology_data))
        logger.info(f"Broadcasted topology data to {len(self.connection_manager.active_connections)} clients")

    async def start(self):
        """Start the FastAPI server"""
        try:
            logger.info(f"Starting TopologyServer on {self.host}:{self.web_port}")
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.web_port,
                log_level="info",
                access_log=True,
                ws_ping_interval=20.0,  # Send ping every 20 seconds
                ws_ping_timeout=30.0,   # Wait 30 seconds for pong response
            )
            server = uvicorn.Server(config)
            logger.info("Server configured, starting to serve...")
            await server.serve()
        except Exception as e:
            logger.error(f"Error starting server: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    server = TopologyServer()
    asyncio.run(server.start())