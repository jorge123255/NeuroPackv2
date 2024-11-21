# nodemanager/master/server.py
import asyncio
import websockets
import json
from typing import Dict
from dataclasses import asdict

class MasterNode:
    def __init__(self, port: int = 8765):
        self.port = port
        self.nodes: Dict[str, DeviceInfo] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        
    async def start(self):
        async with websockets.serve(self.handle_connection, "0.0.0.0", self.port):
            print(f"Master node running on port {self.port}")
            print("Waiting for nodes to connect...")
            await asyncio.Future()  # run forever
            
    async def handle_connection(self, websocket, path):
        try:
            async for message in websocket:
                data = json.loads(message)
                if data['type'] == 'register':
                    node_id = data['data']['id']
                    self.nodes[node_id] = data['data']['device_info']
                    self.connections[node_id] = websocket
                    print(f"\nNew node connected: {node_id}")
                    print(f"Total nodes: {len(self.nodes)}")
                    self.print_cluster_info()
                    
        except websockets.ConnectionClosed:
            # Remove disconnected node
            disconnected = [nid for nid, conn in self.connections.items() if conn == websocket]
            for node_id in disconnected:
                del self.nodes[node_id]
                del self.connections[node_id]
                print(f"\nNode disconnected: {node_id}")
                print(f"Total nodes: {len(self.nodes)}")
                self.print_cluster_info()
                
    def print_cluster_info(self):
        """Print current cluster status"""
        total_cpu = sum(n['cpu_count'] for n in self.nodes.values())
        total_memory = sum(n['total_memory'] for n in self.nodes.values())
        total_gpus = sum(n['gpu_count'] for n in self.nodes.values())
        
        print("\nCluster Resources:")
        print(f"Total CPUs: {total_cpu}")
        print(f"Total Memory: {total_memory/1e9:.1f} GB")
        print(f"Total GPUs: {total_gpus}")
        print("\nNodes:")
        for node_id, info in self.nodes.items():
            print(f"  {info['hostname']} ({node_id[:8]})")
            print(f"    CPU: {info['cpu_count']} cores")
            print(f"    Memory: {info['total_memory']/1e9:.1f} GB")
            if info['gpu_count'] > 0:
                print(f"    GPUs: {info['gpu_count']}")

if __name__ == '__main__':
    master = MasterNode()
    asyncio.run(master.start())