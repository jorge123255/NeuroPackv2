import torch
import time
import GPUtil
from typing import Optional, List, Dict
from dataclasses import dataclass
from torch import amp
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BenchmarkResult:
    size: int
    batch_size: int
    time: float
    tflops: float
    memory_util: float
    gpu0_temp: float
    gpu1_temp: float

class GPUManager:
    def __init__(self):
        self.num_gpus = torch.cuda.device_count()
        assert self.num_gpus >= 2, "This test requires at least 2 GPUs"
        self._setup_gpus()
        logger.info(f"Initialized GPUManager with {self.num_gpus} GPUs")
        
    def _setup_gpus(self):
        """Configure GPUs for optimal performance"""
        for gpu_id in range(self.num_gpus):
            with torch.cuda.device(gpu_id):
                torch.cuda.empty_cache()
                torch.backends.cudnn.benchmark = True
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
        logger.info("GPUs configured for optimal performance")

    def benchmark_matmul(self, size: int, batch_size: int = 4) -> Optional[BenchmarkResult]:
        """Run optimized matrix multiplication benchmark"""
        try:
            self._warmup_gpus(size // 4)
            logger.info(f"Starting benchmark: size={size}, batch_size={batch_size}")
            
            # Generate matrices
            matrices = self._generate_matrices(size, batch_size)
            torch.cuda.synchronize()
            
            # Performance measurement
            start_time = time.perf_counter()
            results = self._parallel_matmul(matrices)
            torch.cuda.synchronize()
            computation_time = time.perf_counter() - start_time
            
            # Calculate metrics
            tflops = (2 * size**3 * batch_size) / (computation_time * 1e12)
            gpu_stats = GPUtil.getGPUs()
            memory_util = sum(gpu.memoryUsed for gpu in gpu_stats) / sum(gpu.memoryTotal for gpu in gpu_stats)
            
            # Cleanup
            del matrices, results
            torch.cuda.empty_cache()
            
            result = BenchmarkResult(
                size=size,
                batch_size=batch_size,
                time=computation_time,
                tflops=tflops,
                memory_util=memory_util * 100,
                gpu0_temp=gpu_stats[0].temperature,
                gpu1_temp=gpu_stats[1].temperature
            )
            
            logger.info(f"Benchmark complete: {tflops:.2f} TFLOPS")
            return result
            
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            torch.cuda.empty_cache()
            return None

    def _generate_matrices(self, size: int, batch_size: int) -> Dict:
        """Generate matrices for multiplication"""
        matrices = {0: {'a': [], 'b': []}, 1: {'a': [], 'b': []}}
        scale = 1.0 / np.sqrt(size)
        
        for gpu_id in range(2):
            batch_per_gpu = batch_size // 2
            with torch.cuda.device(gpu_id):
                for _ in range(batch_per_gpu):
                    matrices[gpu_id]['a'].append(
                        torch.randn(size, size, device=f'cuda:{gpu_id}', 
                                  dtype=torch.float16) * scale
                    )
                    matrices[gpu_id]['b'].append(
                        torch.randn(size, size, device=f'cuda:{gpu_id}', 
                                  dtype=torch.float16) * scale
                    )
        return matrices

    def _parallel_matmul(self, matrices: Dict) -> List[torch.Tensor]:
        """Execute parallel matrix multiplication across GPUs"""
        results = []
        with amp.autocast('cuda'):
            streams = [torch.cuda.Stream(device=i) for i in range(2)]
            
            for gpu_id in range(2):
                with torch.cuda.device(gpu_id):
                    stream = streams[gpu_id]
                    with torch.cuda.stream(stream):
                        for a, b in zip(matrices[gpu_id]['a'], matrices[gpu_id]['b']):
                            results.append(torch.matmul(a, b))
            
            [stream.synchronize() for stream in streams]
        return results

    def _warmup_gpus(self, size: int):
        """Warm up GPUs before benchmark"""
        with amp.autocast('cuda'):
            for gpu_id in range(2):
                with torch.cuda.device(gpu_id):
                    a = torch.randn(size, size, device=f'cuda:{gpu_id}', dtype=torch.float16)
                    b = torch.randn(size, size, device=f'cuda:{gpu_id}', dtype=torch.float16)
                    _ = torch.matmul(a, b)
        torch.cuda.synchronize() 