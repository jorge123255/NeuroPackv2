# neuropack/distributed/worker.py
import asyncio
import logging
import aiohttp
import json
import websockets
from typing import Dict, List, Optional
from .node import Node, DeviceInfo
from dataclasses import asdict

logger = logging.getLogger(__name__)

class WorkerNode(Node):
    def __init__(self, master_host: str, master_port: int = 8765):
        super().__init__(master_host=master_host, master_port=master_port)
        self.ollama_url = "http://localhost:11434/api"
        self.loaded_models: Dict[str, Dict] = {}
        self.active_tasks = {}
        self.model_processes = {}
        self.model_metrics = {}

    async def start(self):
        """Start worker node and connect to master"""
        logger.info(f"Starting worker node, connecting to master at {self.master_host}:{self.master_port}")
        
        try:
            uri = f"ws://{self.master_host}:{self.master_port}"
            async with websockets.connect(uri) as websocket:
                # Register with master
                await self._register(websocket)
                
                # Main worker loop
                while True:
                    try:
                        message = await websocket.recv()
                        await self._handle_message(websocket, message)
                    except websockets.ConnectionClosed:
                        logger.warning("Connection to master lost. Attempting to reconnect...")
                        break
                    except Exception as e:
                        logger.error(f"Error in worker loop: {e}")
                        await asyncio.sleep(1)
                        
        except Exception as e:
            logger.error(f"Worker node error: {e}")
            raise

    async def _register(self, websocket):
        """Register with master node"""
        registration = {
            'type': 'register',
            'id': self.id,
            'device_info': asdict(self.device_info)
        }
        await websocket.send(json.dumps(registration))
        logger.info("Registered with master node")

    async def load_model_shard(self, model_name: str, shard_info: Dict) -> bool:
        """Load a model shard using Ollama"""
        try:
            required_memory = shard_info.get('memory', 0)
            if not self._check_memory_available(required_memory):
                logger.error(f"Insufficient memory for model shard {model_name}")
                return False

            self.model_metrics[model_name] = {
                'requests': 0,
                'tokens': 0,
                'latency_sum': 0,
                'inference_count': 0
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/load",
                    json={
                        "name": model_name,
                        "shard": {
                            "id": shard_info['shard_id'],
                            "layers": shard_info['layers']
                        }
                    }
                ) as response:
                    if response.status == 200:
                        self.loaded_models[model_name] = shard_info
                        await self._send_model_update(websocket)
                        return True
                    return False

        except Exception as e:
            logger.error(f"Error loading model shard: {e}")
            return False

    async def _handle_message(self, websocket, message: str):
        """Handle incoming messages from master"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'load_model':
                success = await self.load_model_shard(
                    data['model_name'],
                    data['shard_info']
                )
                await self._send_status(websocket, 'model_load', success)

            elif msg_type == 'run_inference':
                result = await self._run_inference(
                    data['model_name'],
                    data['input'],
                    data.get('params', {})
                )
                await self._send_result(websocket, data['task_id'], result)

            elif msg_type == 'status_request':
                await self._send_status_update(websocket)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_error(websocket, str(e))

    async def _run_inference(self, model_name: str, input_text: str, params: Dict) -> Dict:
        """Run inference with metrics tracking"""
        if model_name not in self.loaded_models:
            raise ValueError(f"Model {model_name} not loaded on this node")

        start_time = asyncio.get_event_loop().time()
        self.model_metrics[model_name]['requests'] += 1

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/generate",
                    json={
                        "model": model_name,
                        "prompt": input_text,
                        "shard": self.loaded_models[model_name]['shard_id'],
                        **params
                    }
                ) as response:
                    result = await response.json()
                    
                    end_time = asyncio.get_event_loop().time()
                    metrics = self.model_metrics[model_name]
                    metrics['tokens'] += len(result.get('response', '').split())
                    metrics['latency_sum'] += (end_time - start_time)
                    metrics['inference_count'] += 1
                    
                    return result

        except Exception as e:
            logger.error(f"Inference error: {e}")
            raise
        finally:
            self.model_metrics[model_name]['requests'] -= 1

    def _check_memory_available(self, required_memory: int) -> bool:
        """Check if enough GPU memory is available"""
        for gpu in self.device_info.gpu_info:
            free_memory = gpu.total_memory - gpu.current_memory
            if free_memory >= required_memory:
                return True
        return False

    async def _send_status_update(self, websocket):
        """Send status update with model metrics"""
        status = {
            'type': 'status_update',
            'device_info': asdict(self.device_info),
            'loaded_models': self.loaded_models,
            'active_tasks': len(self.active_tasks),
            'model_metrics': {
                name: {
                    'current_requests': metrics['requests'],
                    'total_tokens': metrics['tokens'],
                    'avg_latency': metrics['latency_sum'] / max(metrics['inference_count'], 1)
                }
                for name, metrics in self.model_metrics.items()
            }
        }
        await websocket.send(json.dumps(status))

    async def _send_model_update(self, websocket):
        """Send model update to master"""
        update = {
            'type': 'model_update',
            'models': self.loaded_models
        }
        await websocket.send(json.dumps(update))