import asyncio
import logging
import json
import websockets
from pathlib import Path
import sys
import multiprocessing
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, BackgroundTasks
from starlette.websockets import WebSocketState
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import os
from typing import Set, Dict, Optional
import uuid
import json
import logging
import asyncio
import subprocess
from datetime import datetime
import aiohttp

# Add the parent directory to the Python path so we can import from web package
sys.path.append(str(Path(__file__).parent.parent))
from web.websocket import ConnectionManager

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelDownload:
    def __init__(self):
        self.progress: float = 0
        self.status: str = "pending"  # pending, downloading, completed, failed
        self.error: Optional[str] = None

class TopologyServer:
    def __init__(self, host: str = '0.0.0.0', websocket_port: int = 8765, web_port: int = 8080):
        self.host = host
        self.websocket_port = websocket_port
        self.web_port = web_port
        self.app = FastAPI(title="NeuroPack Topology Server")
        self.connection_manager = ConnectionManager()
        self.latest_topology = None
        self.active_downloads: Dict[str, ModelDownload] = {}
        
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

            @self.app.get("/api/models")
            async def list_models():
                try:
                    # Get Ollama models
                    ollama_models = []
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get('http://localhost:11434/api/tags') as response:
                                if response.status == 200:
                                    data = await response.json()
                                    ollama_models = [
                                        {
                                            "name": f"ollama/{model['name']}", 
                                            "type": "ollama",
                                            "size": model.get('size', 0),
                                            "status": "available"
                                        }
                                        for model in data.get('models', [])
                                    ]
                    except Exception as e:
                        logger.error(f"Error fetching Ollama models: {e}")

                    # Get Hugging Face models from cache
                    hf_models = []
                    cache_dir = Path.home() / '.cache' / 'huggingface'
                    if cache_dir.exists():
                        for model_dir in cache_dir.glob('**/pytorch_model.bin'):
                            model_name = model_dir.parent.parent.name
                            hf_models.append({
                                "name": f"huggingface/{model_name}",
                                "type": "huggingface",
                                "size": model_dir.stat().st_size,
                                "status": "available"
                            })

                    # Always return a valid response with an empty list if no models found
                    return JSONResponse({
                        "models": ollama_models + hf_models if (ollama_models or hf_models) else []
                    })
                except Exception as e:
                    logger.error(f"Error listing models: {e}")
                    # Return empty list instead of error to prevent client-side forEach error
                    return JSONResponse({
                        "models": []
                    })
            
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

            @self.app.post("/api/models/download")
            async def start_model_download(request: dict, background_tasks: BackgroundTasks):
                download_id = str(uuid.uuid4())
                model_name = request.get("model_name")
                source = request.get("source")

                if not model_name:
                    raise HTTPException(status_code=400, detail="Model name is required")

                download = ModelDownload()
                self.active_downloads[download_id] = download

                background_tasks.add_task(
                    self.download_model,
                    model_name,
                    source,
                    download_id
                )

                return JSONResponse({
                    "download_id": download_id,
                    "status": "started"
                })

            @self.app.get("/api/models/download/{download_id}/progress")
            async def get_download_progress(download_id: str):
                download = self.active_downloads.get(download_id)
                if not download:
                    raise HTTPException(status_code=404, detail="Download not found")

                return JSONResponse({
                    "status": download.status,
                    "progress": download.progress,
                    "error": download.error
                })
            
            logger.info("Routes configured successfully")
        except Exception as e:
            logger.error(f"Error setting up routes: {e}", exc_info=True)
            raise

    async def download_model(self, model_name: str, source: str, download_id: str):
        download = self.active_downloads[download_id]
        download.status = "downloading"

        try:
            if source == "huggingface":
                await self.download_from_huggingface(model_name, download)
            elif source == "ollama":
                await self.download_from_ollama(model_name, download)
            else:
                raise ValueError(f"Unsupported source: {source}")

            download.status = "completed"
            download.progress = 100

        except Exception as e:
            download.status = "failed"
            download.error = str(e)
            logger.error(f"Error downloading model {model_name}: {e}")

    async def download_from_huggingface(self, model_name: str, download: ModelDownload):
        """Download a model from Hugging Face"""
        try:
            # Import transformers only when needed
            from transformers import AutoModel, AutoTokenizer
            
            download.progress = 10
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            download.progress = 40
            model = AutoModel.from_pretrained(model_name)
            download.progress = 90

            # Save model info
            model_info = {
                "name": model_name,
                "type": "huggingface",
                "config": model.config.to_dict()
            }

            models_dir = Path("models")
            models_dir.mkdir(exist_ok=True)
            
            model_dir = models_dir / model_name.replace("/", "_")
            model_dir.mkdir(exist_ok=True)

            # Save model files
            model.save_pretrained(str(model_dir))
            tokenizer.save_pretrained(str(model_dir))
            
            # Save model info
            with open(model_dir / "info.json", "w") as f:
                json.dump(model_info, f, indent=2)

            download.progress = 100

        except ImportError:
            raise Exception("Hugging Face transformers package not installed. Please install it first.")
        except Exception as e:
            raise Exception(f"Failed to download from Hugging Face: {str(e)}")

    async def download_from_ollama(self, model_name: str, download: ModelDownload):
        """Download a model from Ollama"""
        try:
            download.progress = 10

            # Use Ollama CLI to pull the model
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise Exception(f"Ollama pull failed: {result.stderr}")

            download.progress = 90

            # Save model info
            model_info = {
                "name": model_name,
                "type": "ollama",
                "pulled_at": str(datetime.now())
            }

            models_dir = Path("models")
            models_dir.mkdir(exist_ok=True)
            
            with open(models_dir / f"{model_name.replace('/', '_')}_info.json", "w") as f:
                json.dump(model_info, f, indent=2)

            download.progress = 100

        except Exception as e:
            raise Exception(f"Failed to download from Ollama: {str(e)}")

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