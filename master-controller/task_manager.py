import asyncio
import logging
from typing import Dict, List, Optional, Any
import uuid
from dataclasses import dataclass
import json
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class NodeResources:
    cpu_count: int
    available_memory: int
    current_tasks: int
    platform: str

class TaskManager:
    def __init__(self):
        self.nodes: Dict[str, NodeResources] = {}
        self.task_queue = asyncio.Queue()
        self.active_tasks: Dict[str, Dict] = {}
        self.task_results: Dict[str, Any] = {}
        
    def register_node(self, node_id: str, resources: Dict):
        """Register a new node with its resources"""
        self.nodes[node_id] = NodeResources(
            cpu_count=resources.get('cpu_count', 0),
            available_memory=resources.get('available_memory', 0),
            current_tasks=0,
            platform=resources.get('platform', 'unknown')
        )
        logger.info(f"Registered node {node_id} with {self.nodes[node_id]}")
        
    def update_node_status(self, node_id: str, status: Dict):
        """Update node status"""
        if node_id in self.nodes:
            self.nodes[node_id] = NodeResources(
                cpu_count=status.get('cpu_count', 0),
                available_memory=status.get('available_memory', 0),
                current_tasks=status.get('task_info', {}).get('active_tasks', 0),
                platform=status.get('platform', 'unknown')
            )
            
    def remove_node(self, node_id: str):
        """Remove a node from the cluster"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            logger.info(f"Removed node {node_id}")
            
    async def distribute_model_weights(self, model_weights: Dict[str, np.ndarray]):
        """Distribute model weights across available nodes"""
        if not self.nodes:
            raise Exception("No nodes available for weight distribution")
            
        # Sort nodes by available memory
        sorted_nodes = sorted(
            self.nodes.items(),
            key=lambda x: (x[1].available_memory, -x[1].current_tasks),
            reverse=True
        )
        
        # Calculate total memory needed
        total_memory = sum(w.nbytes for w in model_weights.values())
        memory_per_node = total_memory / len(sorted_nodes)
        
        # Distribute weights
        distribution: Dict[str, Dict[str, np.ndarray]] = {}
        current_node = 0
        current_memory = 0
        
        for layer_name, weights in model_weights.items():
            node_id = sorted_nodes[current_node][0]
            
            if node_id not in distribution:
                distribution[node_id] = {}
                
            if current_memory + weights.nbytes > memory_per_node and current_node < len(sorted_nodes) - 1:
                current_node += 1
                current_memory = 0
                node_id = sorted_nodes[current_node][0]
                distribution[node_id] = {}
                
            distribution[node_id][layer_name] = weights
            current_memory += weights.nbytes
            
        return distribution
        
    async def create_task(self, task_type: str, data: Dict, priority: int = 1) -> str:
        """Create a new task and add it to queue"""
        task_id = str(uuid.uuid4())
        task = {
            'task_id': task_id,
            'type': 'task',
            'task_type': task_type,
            'data': data,
            'priority': priority
        }
        
        await self.task_queue.put(task)
        self.active_tasks[task_id] = task
        return task_id
        
    def get_best_node(self, memory_required: int = 0) -> Optional[str]:
        """Get the best node for a task based on current resources"""
        available_nodes = [
            (node_id, info) for node_id, info in self.nodes.items()
            if info.available_memory >= memory_required
        ]
        
        if not available_nodes:
            return None
            
        # Sort by available memory and current tasks
        sorted_nodes = sorted(
            available_nodes,
            key=lambda x: (x[1].available_memory, -x[1].current_tasks),
            reverse=True
        )
        
        return sorted_nodes[0][0]
        
    async def handle_task_result(self, node_id: str, result: Dict):
        """Handle task completion result"""
        task_id = result.get('task_id')
        if task_id in self.active_tasks:
            self.task_results[task_id] = result
            del self.active_tasks[task_id]
            
            # Update node status
            if node_id in self.nodes:
                self.nodes[node_id].current_tasks -= 1
                
    def get_cluster_status(self) -> Dict:
        """Get overall cluster status"""
        return {
            'nodes': len(self.nodes),
            'active_tasks': len(self.active_tasks),
            'queued_tasks': self.task_queue.qsize(),
            'completed_tasks': len(self.task_results),
            'resources': {
                node_id: {
                    'cpu_count': info.cpu_count,
                    'available_memory': info.available_memory,
                    'current_tasks': info.current_tasks,
                    'platform': info.platform
                }
                for node_id, info in self.nodes.items()
            }
        }
