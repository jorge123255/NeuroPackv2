import torch
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from torch import amp
import asyncio
from enum import Enum
import aiohttp
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
logger = logging.getLogger(__name__)

class Operation(Enum):
    MATMUL = 'matmul'
    # Add more operations as needed

@dataclass
class TaskResult:
    task_id: str
    result: torch.Tensor
    computation_time: float
    tflops: float
    memory_peak: float

class GPUWorker:
    def __init__(self, device_id: int):
        self.device = torch.device(f'cuda:{device_id}')
        self.device_id = device_id
        self.stream = torch.cuda.Stream(device=self.device)
        
    async def process_chunk(
        self,
        chunk: torch.Tensor,
        full_tensor: torch.Tensor,
        chunk_id: int
    ) -> Tuple[torch.Tensor, float, float]:
        torch.cuda.reset_peak_memory_stats(self.device)
        
        with torch.cuda.device(self.device):
            with torch.cuda.stream(self.stream):
                # Pre-transfer to GPU
                chunk = chunk.to(self.device, non_blocking=True)
                full_tensor = full_tensor.to(self.device, non_blocking=True)
                
                # Ensure transfers are complete
                self.stream.synchronize()
                
                with torch.no_grad():
                    start_event = torch.cuda.Event(enable_timing=True)
                    end_event = torch.cuda.Event(enable_timing=True)
                    
                    start_event.record()
                    result = torch.matmul(chunk, full_tensor.T)
                    end_event.record()
                    
                    # Wait for computation
                    end_event.synchronize()
                    computation_time = start_event.elapsed_time(end_event) / 1000.0
                    memory_used = torch.cuda.max_memory_allocated(self.device) / 1e9
                    
                    logger.info(f"GPU {self.device_id} completed chunk {chunk_id} in {computation_time:.3f}s (Memory: {memory_used:.1f} GB)")
                    
                    # Keep result on GPU
                    del full_tensor
                    torch.cuda.empty_cache()
                    
                    return result, computation_time, memory_used

class DistributedManager:
    def __init__(self, optimal_size: int = 14000):
        self.optimal_size = optimal_size
        self.tasks = []
        self.workers = []
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                self.workers.append(GPUWorker(i))
                logger.info(f"Initialized worker for GPU {i}")
                
    def _get_available_worker(self) -> Optional[GPUWorker]:
        for worker in self.workers:
            if not worker.in_use:
                return worker
        return None

    async def _process_chunks_parallel(
        self,
        chunks: List[torch.Tensor],
        full_tensor: torch.Tensor
    ) -> List[Tuple[torch.Tensor, float, float]]:
        num_chunks = len(chunks)
        num_gpus = len(self.workers)
        results = [None] * num_chunks
        
        # Create fixed assignments of chunks to GPUs
        assignments = [(i, i % num_gpus) for i in range(num_chunks)]
        
        async def process_on_gpu(gpu_id: int):
            gpu_chunks = [(i, chunk) for i, gid in assignments if gid == gpu_id 
                         for chunk in [chunks[i]]]
            worker = self.workers[gpu_id]
            
            for chunk_id, chunk in gpu_chunks:
                tensor_copy = full_tensor.clone()
                result = await worker.process_chunk(chunk, tensor_copy, chunk_id)
                results[chunk_id] = result
                # Force synchronization
                torch.cuda.synchronize(worker.device)
        
        # Launch all GPU tasks simultaneously
        gpu_tasks = [process_on_gpu(gpu_id) for gpu_id in range(num_gpus)]
        await asyncio.gather(*gpu_tasks)
        
        return [r for r in results if r is not None]

    def _split_tensor(self, tensor: torch.Tensor) -> List[torch.Tensor]:
        n = tensor.size(0)
        num_gpus = len(self.workers)
        
        if n <= self.optimal_size:
            return [tensor]
        
        # Calculate chunks based on GPU count
        chunks_per_gpu = (n + self.optimal_size - 1) // self.optimal_size
        total_chunks = chunks_per_gpu * num_gpus
        chunk_size = (n + total_chunks - 1) // total_chunks
        
        chunks = []
        for i in range(0, n, chunk_size):
            end = min(i + chunk_size, n)
            chunk = tensor[i:end, :]
            chunks.append(chunk)
            logger.info(f"Created chunk {len(chunks)-1} of size {chunk.shape}")
        
        logger.info(f"Split into {len(chunks)} chunks across {num_gpus} GPUs")
        return chunks
    
    def _calculate_tflops(self, N: int, computation_time: float) -> float:
        """Calculate TFLOPS for parallel matrix multiplication"""
        # For matrix multiplication: 2 * N^3 operations
        flops = 2.0 * (N ** 3)
        tflops = (flops / computation_time) / 1e12
        return tflops
    
    def _combine_results(
        self,
        results: List[Tuple[torch.Tensor, float, float]],
        operation: Operation,
        original_shape: torch.Size
    ) -> TaskResult:
        tensors = []
        max_time = 0
        memory_per_gpu = [0] * len(self.workers)
        
        # Track memory and timing per GPU
        for i, (result, time, memory) in enumerate(results):
            worker_id = i % len(self.workers)
            tensors.append(result)
            max_time = max(max_time, time)
            memory_per_gpu[worker_id] = max(memory_per_gpu[worker_id], memory)
        
        # Log memory usage per GPU
        for i, mem in enumerate(memory_per_gpu):
            logger.info(f"GPU {i} peak memory: {mem:.1f} GB")
        
        # Move results to GPU 0 and combine
        combined = torch.cat([t.to(self.workers[0].device) for t in tensors], dim=0)
        
        # Calculate effective TFLOPS (accounting for parallel execution)
        total_memory = sum(memory_per_gpu)
        tflops = self._calculate_tflops(original_shape[0], max_time)
        
        return TaskResult(
            task_id=f"task_{len(self.tasks)}",
            result=combined,
            computation_time=max_time,  # Use max time since operations are parallel
            tflops=tflops,
            memory_peak=total_memory
        )

    async def process_large_tensor(
        self,
        tensor: torch.Tensor,
        operation: Operation = Operation.MATMUL
    ) -> Optional[TaskResult]:
        try:
            logger.info(f"Processing tensor of shape {tensor.shape}")
            chunks = self._split_tensor(tensor)
            logger.info(f"Split into {len(chunks)} chunks")
            
            results = await self._process_chunks_parallel(chunks, tensor)
            
            if not results:
                logger.error("No results returned from processing")
                return None
                
            return self._combine_results(results, operation, tensor.shape)
                
        except Exception as e:
            logger.error(f"Error during processing: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None