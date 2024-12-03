"""Load balancing and request routing for distributed model inference."""
import asyncio
from typing import Dict, List, Optional, Tuple
import logging
import random
from datetime import datetime, timedelta
from .node_manager import NodeManager
from ..config.config import ConfigManager, ModelConfig

logger = logging.getLogger(__name__)

class ModelRequest:
    def __init__(self, model_name: str, request_id: str):
        self.model_name = model_name
        self.request_id = request_id
        self.timestamp = datetime.now()
        self.assigned_node: Optional[str] = None
        self.completed = False
        self.error: Optional[str] = None

class LoadBalancer:
    def __init__(self, config_manager: ConfigManager, node_manager: NodeManager):
        self.config_manager = config_manager
        self.node_manager = node_manager
        self.active_requests: Dict[str, ModelRequest] = {}
        self._request_cleanup_task: Optional[asyncio.Task] = None
        self.model_locks: Dict[str, asyncio.Lock] = {}

    async def start(self):
        """Start the load balancer services"""
        self._request_cleanup_task = asyncio.create_task(self._cleanup_old_requests())

    async def stop(self):
        """Stop the load balancer services"""
        if self._request_cleanup_task:
            self._request_cleanup_task.cancel()
            try:
                await self._request_cleanup_task
            except asyncio.CancelledError:
                pass

    def _get_model_lock(self, model_name: str) -> asyncio.Lock:
        """Get or create a lock for a specific model"""
        if model_name not in self.model_locks:
            self.model_locks[model_name] = asyncio.Lock()
        return self.model_locks[model_name]

    async def route_request(self, model_name: str, request_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Route a model inference request to the most suitable node"""
        try:
            request = ModelRequest(model_name, request_id)
            self.active_requests[request_id] = request

            async with self._get_model_lock(model_name):
                node_id = await self._select_best_node(model_name)
                if not node_id:
                    error = "No suitable node available for the model"
                    request.error = error
                    return None, error

                request.assigned_node = node_id
                return node_id, None

        except Exception as e:
            logger.error(f"Error routing request {request_id} for model {model_name}: {e}")
            return None, str(e)

    async def _select_best_node(self, model_name: str) -> Optional[str]:
        """Select the best node for a model request based on load and availability"""
        model_config = self.config_manager.get_model_config(model_name)
        if not model_config:
            logger.error(f"No configuration found for model {model_name}")
            return None

        # Get nodes that can handle this model
        candidate_nodes = self._get_candidate_nodes(model_config)
        if not candidate_nodes:
            return None

        # Apply load balancing strategy
        return await self._apply_load_balancing_strategy(candidate_nodes, model_config)

    def _get_candidate_nodes(self, model_config: ModelConfig) -> List[str]:
        """Get list of nodes that can handle the model"""
        return self.node_manager.get_available_nodes_for_model(model_config.min_gpu_memory)

    async def _apply_load_balancing_strategy(
        self, 
        candidate_nodes: List[str], 
        model_config: ModelConfig
    ) -> Optional[str]:
        """Apply the configured load balancing strategy to select a node"""
        strategy = self.config_manager.system.load_balancing_strategy
        
        if strategy == "round_robin":
            return self._round_robin_selection(candidate_nodes)
        elif strategy == "least_loaded":
            return self._least_loaded_selection(candidate_nodes)
        elif strategy == "random":
            return self._random_selection(candidate_nodes)
        else:
            # Default to least loaded if strategy not recognized
            return self._least_loaded_selection(candidate_nodes)

    def _round_robin_selection(self, candidate_nodes: List[str]) -> Optional[str]:
        """Simple round-robin node selection"""
        if not candidate_nodes:
            return None
        
        # Use the first node and rotate the list
        selected_node = candidate_nodes[0]
        candidate_nodes.append(candidate_nodes.pop(0))
        return selected_node

    def _least_loaded_selection(self, candidate_nodes: List[str]) -> Optional[str]:
        """Select the least loaded node based on GPU utilization"""
        if not candidate_nodes:
            return None

        least_loaded_node = None
        lowest_load = float('inf')

        for node_id in candidate_nodes:
            status = self.node_manager.get_node_status(node_id)
            if not status:
                continue

            # Consider both GPU utilization and number of active models
            load_score = (status.gpu_utilization * 0.7 + 
                         (len(status.current_models) / 
                          self.config_manager.get_node_config(node_id).max_models) * 0.3)

            if load_score < lowest_load:
                lowest_load = load_score
                least_loaded_node = node_id

        return least_loaded_node

    def _random_selection(self, candidate_nodes: List[str]) -> Optional[str]:
        """Random node selection"""
        if not candidate_nodes:
            return None
        return random.choice(candidate_nodes)

    async def _cleanup_old_requests(self):
        """Periodically clean up old requests"""
        while True:
            try:
                current_time = datetime.now()
                timeout = timedelta(seconds=self.config_manager.system.request_timeout)

                # Find and remove old requests
                expired_requests = [
                    request_id for request_id, request in self.active_requests.items()
                    if current_time - request.timestamp > timeout
                ]

                for request_id in expired_requests:
                    del self.active_requests[request_id]

                await asyncio.sleep(60)  # Clean up every minute

            except Exception as e:
                logger.error(f"Error in request cleanup: {e}")
                await asyncio.sleep(60)  # Continue cleanup even if there's an error

    def mark_request_complete(self, request_id: str, error: Optional[str] = None):
        """Mark a request as completed"""
        if request_id in self.active_requests:
            request = self.active_requests[request_id]
            request.completed = True
            request.error = error

    def get_request_status(self, request_id: str) -> Optional[ModelRequest]:
        """Get the status of a specific request"""
        return self.active_requests.get(request_id)

    def get_node_load(self, node_id: str) -> float:
        """Get the current load factor for a node"""
        status = self.node_manager.get_node_status(node_id)
        if not status:
            return float('inf')

        node_config = self.config_manager.get_node_config(node_id)
        if not node_config:
            return float('inf')

        # Calculate load factor based on GPU utilization and model count
        return (status.gpu_utilization * 0.7 + 
                (len(status.current_models) / node_config.max_models) * 0.3)
