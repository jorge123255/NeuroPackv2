import os
import torch
import psutil
from dataclasses import dataclass
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NodeResources:
    cpu_count: int
    memory_total: int
    memory_available: int
    gpu_count: int
    gpu_memory: Dict[int, int]
    gpu_utilization: Dict[int, float]

class Node:
    def __init__(self, node_id: Optional[str] = None):
        self.node_id = node_id or os.getenv('NODE_ID', 'node1')
        self.resources = self._get_resources()
        logger.info(f"Initialized node {self.node_id}")
        
    def _get_resources(self) -> NodeResources:
        # CPU resources
        cpu_count = psutil.cpu_count()
        memory = psutil.virtual_memory()
        
        # GPU resources
        gpu_count = torch.cuda.device_count()
        gpu_memory = {}
        gpu_utilization = {}
        
        for i in range(gpu_count):
            props = torch.cuda.get_device_properties(i)
            gpu_memory[i] = props.total_memory
            # Get current GPU utilization
            gpu_utilization[i] = torch.cuda.utilization(i)
            
        return NodeResources(
            cpu_count=cpu_count,
            memory_total=memory.total,
            memory_available=memory.available,
            gpu_count=gpu_count,
            gpu_memory=gpu_memory,
            gpu_utilization=gpu_utilization
        )
    
    def update_resources(self):
        """Update resource information"""
        self.resources = self._get_resources()
        
    def print_info(self):
        """Print current node information"""
        print(f"\n=== Node {self.node_id} Resources ===")
        print(f"CPUs: {self.resources.cpu_count}")
        print(f"Memory: {self.resources.memory_total / 1024**3:.1f} GB")
        print(f"Available Memory: {self.resources.memory_available / 1024**3:.1f} GB")
        print(f"GPUs: {self.resources.gpu_count}")
        for gpu_id, memory in self.resources.gpu_memory.items():
            print(f"GPU {gpu_id}:")
            print(f"  Memory: {memory / 1024**3:.1f} GB")
            print(f"  Utilization: {self.resources.gpu_utilization[gpu_id]}%")

if __name__ == "__main__":
    node = Node()
    node.print_info()