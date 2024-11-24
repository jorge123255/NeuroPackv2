import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
import json
import psutil
import torch
from pathlib import Path
import aiofiles
import os
from datetime import datetime
import sys

logger = logging.getLogger(__name__)

class TaskType(Enum):
    TOKENIZE = "tokenize"
    CACHE_WEIGHTS = "cache_weights"
    PREPROCESS = "preprocess"
    POSTPROCESS = "postprocess"
    MEMORY_STORE = "memory_store"

@dataclass
class Task:
    task_id: str
    task_type: TaskType
    data: Any
    priority: int = 1
    memory_required: int = 0  # in bytes

class MemoryCache:
    def __init__(self, max_memory_percent: float = 70.0):
        """Initialize memory cache with max percent of system memory to use"""
        self.max_memory_percent = max_memory_percent
        self.cache: Dict[str, Any] = {}
        self.cache_info: Dict[str, Dict] = {}
        self._update_memory_limit()

    def _update_memory_limit(self):
        """Update maximum memory limit based on system available memory"""
        system_memory = psutil.virtual_memory()
        self.max_memory = int(system_memory.total * (self.max_memory_percent / 100))
        self.current_memory = 0

    async def store(self, key: str, data: Any, metadata: Dict = None) -> bool:
        """Store data in cache if memory permits"""
        try:
            # Estimate memory usage of data
            if isinstance(data, (np.ndarray, torch.Tensor)):
                memory_needed = data.nbytes
            elif isinstance(data, (str, bytes)):
                memory_needed = len(data)
            else:
                # For other types, use sys.getsizeof or similar
                memory_needed = sys.getsizeof(data)

            # Check if we have enough memory
            if self.current_memory + memory_needed > self.max_memory:
                logger.warning(f"Not enough memory to cache {key}")
                return False

            # Store data and update memory usage
            self.cache[key] = data
            self.cache_info[key] = {
                'size': memory_needed,
                'metadata': metadata or {},
                'timestamp': datetime.now().isoformat()
            }
            self.current_memory += memory_needed
            return True

        except Exception as e:
            logger.error(f"Error storing data in cache: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve data from cache"""
        return self.cache.get(key)

    async def clear(self, key: str = None):
        """Clear specific key or entire cache"""
        if key:
            if key in self.cache:
                self.current_memory -= self.cache_info[key]['size']
                del self.cache[key]
                del self.cache_info[key]
        else:
            self.cache.clear()
            self.cache_info.clear()
            self.current_memory = 0

class TaskHandler:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.memory_cache = MemoryCache()
        self.active_tasks: Dict[str, Task] = {}
        self.task_queue = asyncio.Queue()
        self.max_concurrent_tasks = os.cpu_count() or 2

    async def handle_task(self, task: Task) -> Dict:
        """Handle different types of tasks"""
        try:
            if task.task_type == TaskType.TOKENIZE:
                return await self._handle_tokenize(task)
            elif task.task_type == TaskType.CACHE_WEIGHTS:
                return await self._handle_cache_weights(task)
            elif task.task_type == TaskType.PREPROCESS:
                return await self._handle_preprocess(task)
            elif task.task_type == TaskType.POSTPROCESS:
                return await self._handle_postprocess(task)
            elif task.task_type == TaskType.MEMORY_STORE:
                return await self._handle_memory_store(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")

        except Exception as e:
            logger.error(f"Error handling task {task.task_id}: {e}")
            return {
                'status': 'error',
                'task_id': task.task_id,
                'error': str(e)
            }

    async def _handle_tokenize(self, task: Task) -> Dict:
        """Handle tokenization tasks"""
        try:
            # Basic tokenization if no specific tokenizer provided
            text = task.data.get('text', '')
            tokenizer = task.data.get('tokenizer', None)
            
            if tokenizer:
                tokens = tokenizer(text)
            else:
                # Simple word-based tokenization as fallback
                tokens = text.split()
            
            return {
                'status': 'success',
                'task_id': task.task_id,
                'tokens': tokens
            }
        except Exception as e:
            raise Exception(f"Tokenization error: {e}")

    async def _handle_cache_weights(self, task: Task) -> Dict:
        """Handle weight caching tasks"""
        try:
            weights_data = task.data.get('weights')
            weights_key = task.data.get('key')
            
            success = await self.memory_cache.store(
                weights_key, 
                weights_data,
                metadata={'type': 'model_weights'}
            )
            
            return {
                'status': 'success' if success else 'error',
                'task_id': task.task_id,
                'cached': success
            }
        except Exception as e:
            raise Exception(f"Weight caching error: {e}")

    async def _handle_preprocess(self, task: Task) -> Dict:
        """Handle preprocessing tasks"""
        try:
            data = task.data.get('input')
            preprocessing_steps = task.data.get('steps', [])
            
            processed_data = data
            for step in preprocessing_steps:
                if step == 'normalize':
                    processed_data = processed_data / 255.0 if isinstance(processed_data, np.ndarray) else processed_data
                elif step == 'reshape':
                    shape = task.data.get('shape')
                    processed_data = np.reshape(processed_data, shape) if shape else processed_data
                    
            return {
                'status': 'success',
                'task_id': task.task_id,
                'processed_data': processed_data
            }
        except Exception as e:
            raise Exception(f"Preprocessing error: {e}")

    async def _handle_postprocess(self, task: Task) -> Dict:
        """Handle postprocessing tasks"""
        try:
            data = task.data.get('output')
            postprocessing_steps = task.data.get('steps', [])
            
            processed_data = data
            for step in postprocessing_steps:
                if step == 'denormalize':
                    processed_data = processed_data * 255.0 if isinstance(processed_data, np.ndarray) else processed_data
                elif step == 'reshape':
                    shape = task.data.get('shape')
                    processed_data = np.reshape(processed_data, shape) if shape else processed_data
                    
            return {
                'status': 'success',
                'task_id': task.task_id,
                'processed_data': processed_data
            }
        except Exception as e:
            raise Exception(f"Postprocessing error: {e}")

    async def _handle_memory_store(self, task: Task) -> Dict:
        """Handle memory storage tasks"""
        try:
            key = task.data.get('key')
            data = task.data.get('data')
            metadata = task.data.get('metadata', {})
            
            success = await self.memory_cache.store(key, data, metadata)
            
            return {
                'status': 'success' if success else 'error',
                'task_id': task.task_id,
                'stored': success
            }
        except Exception as e:
            raise Exception(f"Memory store error: {e}")

    async def start(self):
        """Start task processing"""
        workers = [
            asyncio.create_task(self._process_tasks())
            for _ in range(self.max_concurrent_tasks)
        ]
        await asyncio.gather(*workers)

    async def _process_tasks(self):
        """Process tasks from the queue"""
        while True:
            try:
                task = await self.task_queue.get()
                self.active_tasks[task.task_id] = task
                
                result = await self.handle_task(task)
                
                del self.active_tasks[task.task_id]
                self.task_queue.task_done()
                
                # Notify result through callback or message
                await self._notify_result(result)
                
            except Exception as e:
                logger.error(f"Error processing task: {e}")
                await asyncio.sleep(1)

    async def _notify_result(self, result: Dict):
        """Notify task result to master node"""
        # Implement notification mechanism
        pass

    async def add_task(self, task: Task):
        """Add task to processing queue"""
        await self.task_queue.put(task)

    def get_status(self) -> Dict:
        """Get current status of task handler"""
        return {
            'node_id': self.node_id,
            'active_tasks': len(self.active_tasks),
            'queue_size': self.task_queue.qsize(),
            'memory_usage': {
                'cache_size': self.memory_cache.current_memory,
                'cache_limit': self.memory_cache.max_memory,
                'cache_items': len(self.memory_cache.cache)
            }
        }
