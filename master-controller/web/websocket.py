from fastapi import WebSocket
import json
import logging
from typing import Set
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Add a websocket connection to the manager"""
        self.active_connections.add(websocket)
        logger.info(f"Client {websocket.client.host} connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a websocket connection from the manager"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if websocket.client_state != WebSocketState.DISCONNECTED:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.error(f"Error closing websocket for {websocket.client.host}: {e}")
            logger.info(f"Client {websocket.client.host} disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            logger.debug("No active connections to broadcast to")
            return
            
        logger.debug(f"Broadcasting topology data to {len(self.active_connections)} connections")
        if 'nodes' in message:
            logger.debug(f"Nodes in topology: {len(message['nodes'])}")
            
        json_message = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections:
            if connection.client_state == WebSocketState.DISCONNECTED:
                disconnected.add(connection)
                continue
                
            try:
                await connection.send_text(json_message)
                logger.debug(f"Successfully sent message to {connection.client.host}")
            except Exception as e:
                logger.error(f"Error sending message to {connection.client.host}: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            await self.disconnect(connection)