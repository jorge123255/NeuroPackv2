"""Node management and health monitoring for distributed model system."""
import asyncio
import aiohttp
from typing import Dict, List, Optional, Set
import logging
from datetime import datetime, timedelta
from .metrics import MetricsManager
from ..config.config import ConfigManager, NodeConfig

logger = logging.getLogger(__name__)

class NodeStatus:
    def __init__(self):
        self.is_alive: bool = False
        self.last_heartbeat: Optional[datetime] = None
        self.current_models: Set[str] = set()
        self.gpu_utilization: float = 0.0
        self.memory_utilization: float = 0.0
        self.error_count: int = 0
        self.last_error: Optional[str] = None

class NodeManager:
    def __init__(self, config_manager: ConfigManager, metrics_manager: MetricsManager):
        self.config_manager = config_manager
        self.metrics_manager = metrics_manager
        self.node_status: Dict[str, NodeStatus] = {}
        self.failover_locks: Dict[str, asyncio.Lock] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._initialize_nodes()

    def _initialize_nodes(self):
        """Initialize node status tracking for all configured nodes"""
        for node_id in self.config_manager.nodes:
            self.node_status[node_id] = NodeStatus()
            self.failover_locks[node_id] = asyncio.Lock()

    async def start_health_monitoring(self):
        """Start the health monitoring loop"""
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop_health_monitoring(self):
        """Stop the health monitoring loop"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

    async def _health_check_loop(self):
        """Continuous health check loop for all nodes"""
        while True:
            try:
                await self._check_all_nodes()
                await asyncio.sleep(self.config_manager.system.health_check_interval)
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    async def _check_all_nodes(self):
        """Check health status of all nodes"""
        check_tasks = []
        for node_id, node_config in self.config_manager.nodes.items():
            check_tasks.append(self._check_node_health(node_id, node_config))
        await asyncio.gather(*check_tasks, return_exceptions=True)

    async def _check_node_health(self, node_id: str, node_config: NodeConfig):
        """Check health of a single node"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{node_config.host}:{node_config.port}/health"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._update_node_status(node_id, data)
                    else:
                        await self._handle_node_failure(node_id, f"Health check failed with status {response.status}")
        except Exception as e:
            await self._handle_node_failure(node_id, str(e))

    def _update_node_status(self, node_id: str, health_data: Dict):
        """Update node status with health check data"""
        status = self.node_status[node_id]
        status.is_alive = True
        status.last_heartbeat = datetime.now()
        status.gpu_utilization = health_data.get('gpu_utilization', 0.0)
        status.memory_utilization = health_data.get('memory_utilization', 0.0)
        status.current_models = set(health_data.get('current_models', []))

        # Update metrics
        self.metrics_manager.record_node_status(
            node_id,
            status.gpu_utilization,
            status.memory_utilization,
            len(status.current_models)
        )

    async def _handle_node_failure(self, node_id: str, error_msg: str):
        """Handle node failure and initiate failover if necessary"""
        async with self.failover_locks[node_id]:
            status = self.node_status[node_id]
            status.is_alive = False
            status.error_count += 1
            status.last_error = error_msg
            
            logger.error(f"Node {node_id} failed: {error_msg}")
            
            # Check if failover is needed
            if self._should_initiate_failover(status):
                await self._initiate_failover(node_id)

    def _should_initiate_failover(self, status: NodeStatus) -> bool:
        """Determine if failover should be initiated based on node status"""
        if not status.last_heartbeat:
            return True
        
        timeout = timedelta(seconds=self.config_manager.system.timeout)
        return (
            datetime.now() - status.last_heartbeat > timeout and
            status.error_count >= self.config_manager.system.retry_attempts
        )

    async def _initiate_failover(self, failed_node_id: str):
        """Initiate failover process for a failed node"""
        try:
            # Get models that need to be redistributed
            failed_models = self.node_status[failed_node_id].current_models
            if not failed_models:
                return

            # Find available nodes for failover
            available_nodes = [
                node_id for node_id, status in self.node_status.items()
                if node_id != failed_node_id and status.is_alive
            ]

            if not available_nodes:
                logger.error("No available nodes for failover")
                return

            # Redistribute models
            for model_name in failed_models:
                model_config = self.config_manager.get_model_config(model_name)
                if not model_config:
                    continue

                # Find best node for this model
                target_node = await self._find_best_failover_node(
                    available_nodes,
                    model_config.min_gpu_memory
                )
                
                if target_node:
                    await self._migrate_model(model_name, failed_node_id, target_node)
                else:
                    logger.error(f"No suitable node found for model {model_name}")

        except Exception as e:
            logger.error(f"Error during failover for node {failed_node_id}: {e}")

    async def _find_best_failover_node(self, available_nodes: List[str], required_memory: int) -> Optional[str]:
        """Find the best node for failover based on current utilization"""
        best_node = None
        lowest_utilization = float('inf')

        for node_id in available_nodes:
            status = self.node_status[node_id]
            node_config = self.config_manager.get_node_config(node_id)
            
            if not node_config or not status.is_alive:
                continue

            if (len(status.current_models) < node_config.max_models and 
                node_config.gpu_memory >= required_memory):
                
                if status.gpu_utilization < lowest_utilization:
                    lowest_utilization = status.gpu_utilization
                    best_node = node_id

        return best_node

    async def _migrate_model(self, model_name: str, from_node: str, to_node: str):
        """Migrate a model from one node to another"""
        logger.info(f"Migrating model {model_name} from {from_node} to {to_node}")
        try:
            # Load model on new node
            node_config = self.config_manager.get_node_config(to_node)
            async with aiohttp.ClientSession() as session:
                url = f"http://{node_config.host}:{node_config.port}/load_model"
                async with session.post(url, json={'model_name': model_name}) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to load model on new node: {response.status}")

            # Update status
            self.node_status[to_node].current_models.add(model_name)
            if from_node in self.node_status:
                self.node_status[from_node].current_models.discard(model_name)

            # Record metrics
            self.metrics_manager.record_model_migration(model_name, from_node, to_node)

        except Exception as e:
            logger.error(f"Error migrating model {model_name}: {e}")
            raise

    def get_node_status(self, node_id: str) -> Optional[NodeStatus]:
        """Get current status of a node"""
        return self.node_status.get(node_id)

    def get_all_node_status(self) -> Dict[str, NodeStatus]:
        """Get current status of all nodes"""
        return self.node_status

    def get_available_nodes_for_model(self, required_memory: int) -> List[str]:
        """Get list of nodes that can handle a model with given memory requirements"""
        return [
            node_id for node_id, status in self.node_status.items()
            if (status.is_alive and
                self.config_manager.get_node_config(node_id).gpu_memory >= required_memory)
        ]
