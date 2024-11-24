import asyncio
import logging
import sys
import os
import websockets
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ollama_distribution():
    """Test client for distributed inference"""
    try:
        # Connect to existing master node
        uri = "ws://localhost:8765"
        async with websockets.connect(uri) as websocket:
            logger.info("Connected to master node")
            
            # Register as a client
            register_msg = {
                "type": "register",
                "role": "client",
                "id": f"test_client_{int(time.time())}"
            }
            await websocket.send(json.dumps(register_msg))
            
            # Wait for registration confirmation
            reg_response = await websocket.recv()
            logger.info(f"Registration response: {reg_response}")
            
            # Test inference request
            request = {
                "type": "inference",
                "model": "mistral:7b",
                "prompt": "What is distributed computing?",
                "stream": True,  # Enable streaming
                "parameters": {
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            }
            
            # Send request
            logger.info(f"\nSending request: {request}")
            await websocket.send(json.dumps(request))
            
            # Collect the full response
            full_response = []
            
            # Wait for and process streaming responses
            while True:
                try:
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    
                    if response_data.get("type") == "error":
                        logger.error(f"Error from server: {response_data.get('message')}")
                        break
                    
                    if response_data.get("type") == "stream":
                        text = response_data.get("text", "")
                        full_response.append(text)
                        logger.info(f"Received chunk: {text}")
                        
                    if response_data.get("type") == "inference_complete":
                        logger.info("\nInference complete!")
                        break
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Connection closed by server")
                    break
            
            logger.info("\nFull response:")
            logger.info("".join(full_response))
            
            # Get metrics
            try:
                metrics_request = {"type": "get_metrics"}
                await websocket.send(json.dumps(metrics_request))
                metrics = await websocket.recv()
                metrics_data = json.loads(metrics)
                
                logger.info("\nSystem Metrics:")
                for node_id, node_metrics in metrics_data.items():
                    logger.info(f"\nNode {node_id}:")
                    logger.info(f"CPU Usage: {node_metrics.get('cpu_usage', 'N/A')}%")
                    logger.info(f"Memory Usage: {node_metrics.get('memory_usage', 'N/A')}%")
                    if node_metrics.get('gpu_info'):
                        for gpu in node_metrics['gpu_info']:
                            logger.info(f"GPU {gpu['index']}: {gpu['utilization']}%")
            
            except Exception as e:
                logger.error(f"Error getting metrics: {e}")
    
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"WebSocket connection closed: {e}")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_ollama_distribution()) 