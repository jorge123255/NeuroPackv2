import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from gpu_manager import GPUManager
import time

def run_benchmark():
    benchmark = GPUManager()
    
    # Optimal configurations
    configs = [
        (12000, 8),
        (14000, 6),
        (16000, 4),
        (18000, 2)
    ]
    
    results = []
    for size, batch_size in configs:
        print(f"\n=== Testing {size}x{size} matrices (batch_size={batch_size}) ===")
        result = benchmark.benchmark_matmul(size, batch_size)
        
        if result:
            results.append(result)
            print(f"Time: {result.time:.3f} seconds")
            print(f"TFLOPS: {result.tflops:.2f}")
            print(f"Memory Utilization: {result.memory_util:.1f}%")
            print(f"GPU Temperatures: {result.gpu0_temp:.1f}°C, {result.gpu1_temp:.1f}°C")
        
        time.sleep(2)  # Cool down period
    
    if results:
        print("\n=== Performance Summary ===")
        avg_tflops = sum(r.tflops for r in results) / len(results)
        max_tflops = max(r.tflops for r in results)
        print(f"\nAverage TFLOPS: {avg_tflops:.2f}")
        print(f"Peak TFLOPS: {max_tflops:.2f}")
        
        print("\nDetailed Results:")
        for result in results:
            print(f"\nMatrix Size: {result.size}x{result.size}")
            print(f"Batch Size: {result.batch_size}")
            print(f"Time: {result.time:.3f} seconds")
            print(f"TFLOPS: {result.tflops:.2f}")
            print(f"Memory Utilization: {result.memory_util:.1f}%")
            print(f"GPU Temperatures: {result.gpu0_temp:.1f}°C, {result.gpu1_temp:.1f}°C")

if __name__ == "__main__":
    run_benchmark()