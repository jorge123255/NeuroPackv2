# neuropack/distributed/model_manager.py
from typing import Dict, List, Optional
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self):
        self.loaded_models: Dict[str, Dict] = {}  # model_name -> {node_id: shard_info}
        self.model_configs: Dict[str, Dict] = {}  # Configurations for each model
        self.ollama_base_url = "http://localhost:11434"  # Ollama API endpoint

    async def list_available_models(self) -> List[str]:
        """List all available models from Ollama"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.ollama_base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    return [model['name'] for model in data['models']]
                return []

    async def load_model(self, model_name: str, node_ids: List[str]) -> bool:
        """Load a model across multiple nodes"""
        try:
            # Get model info from Ollama
            model_info = await self._get_model_info(model_name)
            if not model_info:
                return False

            # Calculate model sharding based on available nodes
            shards = self._calculate_model_shards(model_info, len(node_ids))
            
            # Distribute model across nodes
            for node_id, shard in zip(node_ids, shards):
                self.loaded_models.setdefault(model_name, {})[node_id] = {
                    'shard_id': shard['id'],
                    'layers': shard['layers'],
                    'memory_required': shard['memory']
                }

            return True

        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            return False

    async def _get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get model information from Ollama"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.ollama_base_url}/api/show/{model_name}") as response:
                if response.status == 200:
                    return await response.json()
                return None

    def _calculate_model_shards(self, model_info: Dict, num_nodes: int) -> List[Dict]:
        """Calculate how to split model across nodes"""
        total_layers = model_info.get('num_layers', 1)
        layers_per_node = total_layers // num_nodes

        shards = []
        for i in range(num_nodes):
            start_layer = i * layers_per_node
            end_layer = start_layer + layers_per_node if i < num_nodes - 1 else total_layers
            
            shards.append({
                'id': i,
                'layers': list(range(start_layer, end_layer)),
                'memory': model_info.get('memory_per_layer', 0) * (end_layer - start_layer)
            })

        return shards