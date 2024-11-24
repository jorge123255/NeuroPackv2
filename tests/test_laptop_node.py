import asyncio
import json
import logging
import platform
import psutil
import time
import websockets
from dataclasses import dataclass
import aiohttp

# Configuration
WEBSOCKET_URL = "ws://192.168.1.230:8765"
OLLAMA_API_URL = "http://localhost:11434"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DeviceInfo:
    cpu_count: int
    cpu_freq: float
    total_memory: int
    available_memory: int
    gpu_count: int
    gpu_info: list
    ip_address: str
    hostname: str
    platform: str

    def to_dict(self):
        return {
            'cpu_count': self.cpu_count,
            'cpu_freq': self.cpu_freq,
            'total_memory': self.total_memory,
            'available_memory': self.available_memory,
            'gpu_count': self.gpu_count,
            'gpu_info': self.gpu_info,
            'ip_address': self.ip_address,
            'hostname': self.hostname,
            'platform': self.platform
        }

async def handle_inference(websocket, data):
    try:
        model = data.get('model')
        messages = data.get('messages', [])
        stream = data.get('stream', False)
        client_id = data.get('client_id')
        options = data.get('options', {})

        async with aiohttp.ClientSession() as session:
            payload = {
                'model': model,
                'messages': messages,
                'stream': stream,
                **options
            }
            
            async with session.post('http://localhost:11434/api/chat', json=payload) as resp:
                if stream:
                    async for line in resp.content:
                        if line:
                            chunk = json.loads(line)
                            response = {
                                'type': 'inference_response',
                                'client_id': client_id,
                                'response': chunk.get('message', {}).get('content', ''),
                                'status': 'success'
                            }
                            await websocket.send(json.dumps(response))
                else:
                    result = await resp.json()
                    return {
                        'type': 'inference_response',
                        'client_id': client_id,
                        'response': result.get('message', {}).get('content', ''),
                        'status': 'success'
                    }

    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        return {
            'type': 'inference_response',
            'client_id': client_id,
            'status': 'error',
            'error': str(e)
        }

async def test_worker_connection():
    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            # Send registration
            registration = create_registration_message()
            await websocket.send(json.dumps(registration))
            
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    logger.info(f"Worker received: {data}")

                    if data['type'] == 'heartbeat':
                        response = create_heartbeat_response()
                        await websocket.send(json.dumps(response))
                        
                    elif data['type'] == 'inference':
                        logger.info(f"Processing inference request: {data}")
                        response = await handle_inference(websocket, data)
                        if not data.get('stream', False):
                            await websocket.send(json.dumps(response))
                            
                except websockets.exceptions.ConnectionClosed:
                    logger.error("Connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error in message loop: {e}")
                    continue

    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(test_worker_connection())
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}") 