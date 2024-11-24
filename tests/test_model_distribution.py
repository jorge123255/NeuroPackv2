# tests/test_model_distribution.py
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from neuropack.distributed.master import MasterNode
import logging
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_model_distribution():
    try:
        master = MasterNode()
        await master.start()
        
        # Print GPU info
        print("\nGPU Information:")
        if torch.cuda.is_available():
            print(f"Number of GPUs: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
                print(f"Memory Allocated: {torch.cuda.memory_allocated(i)/1e9:.1f} GB")
        
        # Wait for nodes to connect
        print("\nWaiting for nodes to connect...")
        await asyncio.sleep(10)
        
        # Print connected nodes
        print("\nConnected Nodes:")
        for node_id, info in master.nodes.items():
            print(f"Node {node_id}: {info}")
            
        # Test loading Mistral-7B
        model_name = "mistral-7b"
        print(f"\nAttempting to load {model_name} distributed...")
        success = await master.load_model(model_name, distributed=True)
        
        if success:
            print("\nModel Distribution:")
            for node_id, layers in master.model_shards.get(model_name, {}).items():
                print(f"Node {node_id}: Layers {layers}")
                if node_id in master.performance_metrics:
                    metrics = master.performance_metrics[node_id]
                    print(f"  Memory Usage: {metrics.get('memory_usage', 'N/A')}%")
                    print(f"  GPU Memory: {metrics.get('gpu_memory', 'N/A')} GB")
        else:
            print("Failed to load model")
            
        # Keep running to maintain connections
        print("\nKeeping connections alive. Press Ctrl+C to exit...")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await master.shutdown()

if __name__ == "__main__":
    asyncio.run(test_model_distribution())