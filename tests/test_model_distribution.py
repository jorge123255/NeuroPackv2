# tests/test_model_distribution.py
import asyncio
import pytest
from neuropack.distributed.master import MasterNode, ModelInfo
from neuropack.distributed.worker import WorkerNode

@pytest.fixture
async def master_node():
    """Fixture for master node setup and teardown"""
    master = MasterNode(port=8765)
    master_task = asyncio.create_task(master.start())
    await asyncio.sleep(1)  # Wait for startup
    yield master
    master_task.cancel()
    await asyncio.gather(master_task, return_exceptions=True)

@pytest.fixture
async def worker_nodes():
    """Fixture for worker nodes setup and teardown"""
    workers = []
    tasks = []
    try:
        for port in range(8766, 8768):
            worker = WorkerNode(master_host='localhost', master_port=8765)
            workers.append(worker)
            tasks.append(asyncio.create_task(worker.start()))
        await asyncio.sleep(1)
        yield workers
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

@pytest.mark.asyncio
async def test_model_distribution(master_node, worker_nodes):
    """Test model distribution functionality"""
    # Test model listing
    models = await master_node.list_available_models()
    assert len(models) > 0, "No models available from Ollama"
    
    # Test model loading with distribution
    model_name = "mistral-7b"
    success = await master_node.load_model(model_name, distributed=True)
    assert success, f"Failed to load {model_name}"
    
    # Verify model distribution
    assert model_name in master_node.model_shards, "Model not registered in master shards"
    assert len(master_node.model_shards[model_name]) > 0, "No shards allocated"
    
    # Check if workers loaded their shards
    await asyncio.sleep(2)  # Wait for shard loading
    loaded_workers = 0
    for worker in worker_nodes:
        if model_name in worker.loaded_models:
            loaded_workers += 1
    assert loaded_workers > 0, "No workers loaded model shards"

@pytest.mark.asyncio
async def test_model_fallback(master_node):
    """Test single-node fallback when distribution not possible"""
    # Test loading without distribution
    success = await master_node.load_model("mistral-7b", distributed=False)
    assert success, "Failed to load model in single-node mode"
    
    # Verify single worker loaded full model
    await asyncio.sleep(2)
    assert "mistral-7b" in master_node.loaded_models
    assert not master_node.loaded_models["mistral-7b"].get('shard_id')

@pytest.mark.asyncio
async def test_model_metrics(master_node):
    """Test model performance metrics"""
    model_name = "mistral-7b"
    await master_node.load_model(model_name)
    await asyncio.sleep(2)

    # Verify metrics initialization
    model_info = master_node.available_models.get(model_name)
    assert model_info is not None
    assert model_info.current_requests == 0
    assert model_info.total_tokens == 0

@pytest.mark.asyncio
async def test_error_handling(master_node):
    """Test error handling scenarios"""
    # Test invalid model name
    success = await master_node.load_model("nonexistent-model")
    assert not success, "Should fail for invalid model"

def test_model_shard_calculation():
    """Test shard calculation logic"""
    master = MasterNode()
    model_info = {
        'size': 1000,
        'num_layers': 10
    }
    gpus = {
        'node1': {'free_memory': 600},
        'node2': {'free_memory': 400}
    }
    
    shards = master._calculate_model_shards(model_info, gpus)
    assert len(shards) == 2, "Incorrect number of shards"
    assert sum(len(s['layers']) for s in shards) == 10, "Incorrect layer distribution"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])