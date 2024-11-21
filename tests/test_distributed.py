import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from neuropack.core.distributed_manager import DistributedManager, Operation
import torch
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_distributed_processing():
    try:
        print("Initializing DistributedManager...")
        manager = DistributedManager()
        
        # Print GPU info
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"Number of GPUs: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
                print(f"Memory Allocated: {torch.cuda.memory_allocated(i)/1e9:.1f} GB")
        
        # Test sizes
        sizes = [14000, 28000, 42000]
        
        for size in sizes:
            print(f"\nTesting with size {size}x{size}")
            test_tensor = torch.randn(size, size)
            
            result = await manager.process_large_tensor(test_tensor, Operation.MATMUL)
            
            if result:
                print("\n=== Results ===")
                print(f"Matrix Size: {size}x{size}")
                print(f"Total Computation Time: {result.computation_time:.3f} seconds")
                print(f"TFLOPS: {result.tflops:.2f}")
                print(f"Peak Memory: {result.memory_peak:.1f} GB")
                print(f"Output Shape: {result.result.shape}")
                
                # Print per-GPU memory usage
                for i in range(torch.cuda.device_count()):
                    print(f"GPU {i} Memory: {torch.cuda.memory_allocated(i)/1e9:.1f} GB")
                    
                # Clear GPU memory
                torch.cuda.empty_cache()
            else:
                print("Processing failed!")
                
    except Exception as e:
        print(f"Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting test...")
    asyncio.run(test_distributed_processing())
    print("Test completed.")
