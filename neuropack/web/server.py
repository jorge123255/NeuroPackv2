from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from pathlib import Path

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

class TopologyServer:
    def __init__(self, master_node):
        self.master_node = master_node
        self.connected_clients = set()
        
    async def broadcast_topology(self):
        """Broadcast topology updates to all connected clients"""
        while True:
            if self.connected_clients:
                topology_data = {
                    'nodes': [],
                    'links': []
                }
                
                # Add master node
                topology_data['nodes'].append({
                    'id': 'master',
                    'label': 'Master Node',
                    'type': 'master',
                    'gpu_count': len(self.master_node.get_gpu_info()),
                })
                
                # Add connected nodes
                for name, node_data in self.master_node.nodes.items():
                    node_info = node_data.get('node_info', {})
                    resources = node_info.get('resources', {})
                    system = node_info.get('system_info', {})
                    
                    topology_data['nodes'].append({
                        'id': name,
                        'label': name,
                        'type': node_data.get('node_type', 'unknown'),
                        'cpu_usage': resources.get('cpu_percent', 0),
                        'memory_usage': resources.get('memory', {}).get('percent', 0),
                        'gpu_info': system.get('gpu_info', []),
                        'platform': system.get('platform', 'Unknown')
                    })
                    
                    # Add connection to master
                    topology_data['links'].append({
                        'source': 'master',
                        'target': name,
                        'value': 1  # Connection strength
                    })
                
                # Broadcast to all clients
                for client in self.connected_clients:
                    try:
                        await client.send_json(topology_data)
                    except:
                        pass
                        
            await asyncio.sleep(1)  # Update every second

    async def websocket_endpoint(self, websocket: WebSocket):
        await websocket.accept()
        self.connected_clients.add(websocket)
        try:
            while True:
                await websocket.receive_text()  # Keep connection alive
        except:
            self.connected_clients.remove(websocket) 