import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
import asyncio
import logging
import torch
import numpy as np
from master_controller.task_manager import TaskManager
from Devices.task_handler import TaskHandler, Task, TaskType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_task_distribution():
    """Test task distribution between master and worker nodes"""
    try:
        # Initialize task manager (master node)
        task_manager = TaskManager()
        
        # Initialize task handlers (worker nodes)
        worker1 = TaskHandler("worker1")
        worker2 = TaskHandler("worker2")
        
        # Start workers
        worker1_task = asyncio.create_task(worker1.start())
        worker2_task = asyncio.create_task(worker2.start())
        
        # Register workers with task manager
        task_manager.register_node("worker1", {
            "cpu_count": 4,
            "available_memory": 8000000000,  # 8GB
            "platform": "test"
        })
        
        task_manager.register_node("worker2", {
            "cpu_count": 4,
            "available_memory": 8000000000,  # 8GB
            "platform": "test"
        })
        
        # Create test model weights
        test_weights = {
            "layer1": torch.randn(1000, 1000).numpy(),
            "layer2": torch.randn(1000, 1000).numpy(),
            "layer3": torch.randn(1000, 1000).numpy()
        }
        
        # Test weight distribution
        print("\nTesting weight distribution...")
        distribution = await task_manager.distribute_model_weights(test_weights)
        assert len(distribution) > 0, "Weight distribution failed"
        print(f"Weights distributed across {len(distribution)} nodes")
        
        # Test task creation and distribution
        print("\nTesting task creation and distribution...")
        tasks = []
        for i in range(5):
            task_id = await task_manager.create_task(
                task_type="TOKENIZE",
                data={"text": f"Test text {i}", "memory_required": 1000000},
                priority=i
            )
            tasks.append(task_id)
            
        assert len(tasks) == 5, "Task creation failed"
        print(f"Created {len(tasks)} tasks")
        
        # Test task assignment
        print("\nTesting task assignment...")
        for task in tasks:
            success = await task_manager.assign_task({
                "task_id": task,
                "type": "task",
                "task_type": "TOKENIZE",
                "data": {"text": "Test text", "memory_required": 1000000},
                "priority": 1
            })
            assert success, f"Task assignment failed for task {task}"
        
        # Test cluster status
        print("\nTesting cluster status...")
        status = task_manager.get_cluster_status()
        assert status["nodes"] == 2, "Incorrect number of nodes"
        assert status["active_tasks"] == 5, "Incorrect number of active tasks"
        print("Cluster status:", status)
        
        # Clean up
        await worker1.stop()
        await worker2.stop()
        worker1_task.cancel()
        worker2_task.cancel()
        
        print("\nAll tests passed successfully!")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        raise

@pytest.mark.asyncio
async def test_memory_cache():
    """Test memory cache functionality"""
    try:
        handler = TaskHandler("test_worker")
        
        # Test data storage
        print("\nTesting data storage...")
        data = torch.randn(1000, 1000)
        handler.cache.store("test_data", data)
        
        # Verify storage
        assert "test_data" in handler.cache.cache
        print("Data stored successfully")
        
        # Test memory limits
        print("\nTesting memory limits...")
        large_data = torch.randn(10000, 10000)
        handler.cache.store("large_data", large_data)
        
        # Verify cache size is within limits
        total_size = sum(obj.nbytes for obj in handler.cache.cache.values())
        system_memory = handler.cache.get_system_memory()
        assert total_size < system_memory * 0.7, "Cache size exceeds limit"
        print("Memory limits working correctly")
        
        print("\nMemory cache tests passed successfully!")
        
    except Exception as e:
        logger.error(f"Error during memory cache test: {e}")
        raise

if __name__ == "__main__":
    print("Starting distributed system tests...")
    asyncio.run(test_task_distribution())
    asyncio.run(test_memory_cache())
    print("All tests completed successfully!")
