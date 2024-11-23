# nodemanager/scripts/join_cluster.py
import asyncio
import websockets
import json
import click
from pathlib import Path

@click.command()
@click.option('--master', default='ws://localhost:8765', help='Master node websocket address')
async def join_cluster(master: str):
    """Join the distributed compute cluster"""
    try:
        print(f"Connecting to master node at {master}...")
        async with websockets.connect(master) as websocket:
            # Send initial registration
            node = Node()
            await websocket.send(json.dumps({
                'type': 'register',
                'data': node.to_dict()
            }))
            
            print(f"Registered as node {node.id}")
            print("Device information:")
            print(f"  CPU: {node.device_info.cpu_count} cores @ {node.device_info.cpu_freq/1000:.1f} GHz")
            print(f"  Memory: {node.device_info.total_memory/1e9:.1f} GB")
            if node.device_info.gpu_count > 0:
                print(f"  GPUs: {node.device_info.gpu_count}")
                for gpu in node.device_info.gpu_info:
                    print(f"    - {gpu['name']} ({gpu['total_memory']/1e9:.1f} GB)")
            
            # Keep connection alive and handle commands
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                await handle_message(websocket, data, node)
                
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Failed to connect to master node. Is it running?")

async def handle_message(websocket, data: Dict, node: Node):
    """Handle incoming messages from master"""
    msg_type = data.get('type')
    if msg_type == 'ping':
        await websocket.send(json.dumps({
            'type': 'pong',
            'data': {
                'id': node.id,
                'timestamp': time.time()
            }
        }))

if __name__ == '__main__':
    asyncio.run(join_cluster())