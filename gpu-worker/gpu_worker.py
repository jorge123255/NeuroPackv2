import asyncio
import logging
import os
import sys
import uuid
import json
import websockets
from neuropack.distributed.node import Node, DeviceInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d-%b-%y %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GPUWorkerNode(Node):
    """GPU Worker node that extends the base Node class"""
    def __init__(self, master_host: str, master_port: int = 8765):
        super().__init__(master_host, master_port)
        # Set role to gpu-worker since we know this is a GPU node
        self.device_info.role = "gpu-worker"
        # Ensure we have a unique ID
        self.id = f"gpu-worker-{str(uuid.uuid4())}"
        self._heartbeat_task = None
        self._status_task = None
        self._message_handler_task = None
        self._connected = False
        self._ws = None
        
    async def _send_heartbeat(self):
        """Send periodic heartbeat to master"""
        while self._connected:
            try:
                if self._ws:
                    heartbeat = {
                        'type': 'heartbeat_response',
                        'id': self.id,
                        'timestamp': asyncio.get_event_loop().time()
                    }
                    await self._ws.send(json.dumps(heartbeat))
                await asyncio.sleep(30)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                await asyncio.sleep(5)

    async def _send_status_updates(self):
        """Send periodic status updates to master"""
        while self._connected:
            try:
                if self._ws:
                    status = {
                        'type': 'status_update',
                        'id': self.id,
                        'device_info': self.device_info.__dict__,
                        'timestamp': asyncio.get_event_loop().time()
                    }
                    await self._ws.send(json.dumps(status))
                await asyncio.sleep(5)
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"Error sending status update: {e}")
                await asyncio.sleep(5)

    async def _handle_master_messages(self):
        """Handle incoming messages from master"""
        while self._connected:
            try:
                if self._ws:
                    message = await self._ws.recv()
                    data = json.loads(message)
                    
                    if data.get('type') == 'heartbeat':
                        response = {
                            'type': 'heartbeat_response',
                            'id': self.id,
                            'timestamp': asyncio.get_event_loop().time()
                        }
                        await self._ws.send(json.dumps(response))
                    elif data.get('type') == 'register_ack':
                        logger.info(f"Registration acknowledged by master")
                    else:
                        logger.debug(f"Received message from master: {data}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("Master connection closed")
                break
            except Exception as e:
                logger.error(f"Error handling master message: {e}")
                await asyncio.sleep(1)

    async def connect_to_master(self):
        """Connect to master node with proper connection handling"""
        while True:
            try:
                logger.info(f"Connecting to master at {self.master_uri}")
                
                async with websockets.connect(self.master_uri) as websocket:
                    self._ws = websocket
                    self._connected = True
                    
                    # Send initial registration
                    register_msg = {
                        'type': 'register',
                        'id': self.id,
                        'device_info': self.device_info.__dict__
                    }
                    await websocket.send(json.dumps(register_msg))
                    logger.info(f"Registered with master as {self.id}")

                    # Start background tasks
                    tasks = []
                    tasks.append(asyncio.create_task(self._send_heartbeat()))
                    tasks.append(asyncio.create_task(self._send_status_updates()))
                    tasks.append(asyncio.create_task(self._handle_master_messages()))

                    # Wait for any task to complete (which likely means connection lost)
                    try:
                        await asyncio.gather(*tasks)
                    except Exception as e:
                        logger.error(f"Task error: {e}")
                    finally:
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        
            except websockets.exceptions.ConnectionClosed:
                logger.error("Connection to master closed")
            except Exception as e:
                logger.error(f"Connection error: {e}")
            finally:
                self._connected = False
                self._ws = None
                await asyncio.sleep(5)  # Wait before retrying
        
    async def start(self):
        """Start the GPU worker node"""
        while True:
            try:
                logger.info(f"Starting GPU worker node {self.id}, connecting to master at {self.master_uri}")
                await self.connect_to_master()
            except Exception as e:
                logger.error(f"Error in GPU worker node: {e}")
                await asyncio.sleep(5)

async def main():
    try:
        # Get master connection details from environment
        master_host = os.getenv('MASTER_HOST', '192.168.1.231')
        master_port = int(os.getenv('MASTER_PORT', '8765'))
        
        logger.info(f"Initializing GPU worker node to connect to {master_host}:{master_port}")
        
        # Create and start GPU worker node
        node = GPUWorkerNode(master_host, master_port)
        
        # Handle shutdown gracefully
        try:
            await node.start()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Error running GPU worker: {e}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to initialize GPU worker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down GPU worker node")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
