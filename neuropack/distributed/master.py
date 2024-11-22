import asyncio
import json
import logging
import multiprocessing
from typing import Dict, Set, List
import websockets
from dataclasses import asdict
from neuropack.web.server import TopologyServer
from neuropack.distributed.node import Node, DeviceInfo

logger = logging.getLogger(__name__)

class MasterNode(Node):
    def __init__(self, host="0.0.0.0", port=8765, web_port=8080):
        super().__init__(master_host=host, master_port=port)
        self.host = host
        self.port = port
        self.web_port = web_port
        self.is_master = True
        self.nodes: Dict[str, DeviceInfo] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.web_server = None
        self.model_registry: Dict[str, Dict[str, ModelInfo]] = {}  # node_id -> {model_name: ModelInfo}
        self.task_queue = asyncio.Queue()
        self.performance_metrics = {}
        
    async def start(self):
        """Start the master node and web interface"""
        logger.info(f"Starting master node on {self.host}:{self.port}")
        
        # Add self to nodes with master info
        self.nodes[self.id] = self.device_info
        
        # Create web server in the same event loop
        self.web_server = TopologyServer(host=self.host, port=self.web_port)
        
        # Start monitoring tasks
        self.monitor_task = asyncio.create_task(self._monitor_cluster())
        self.metrics_task = asyncio.create_task(self._collect_metrics())
        
        try:
            await asyncio.gather(
                self.web_server.start(),
                websockets.serve(self.handle_connection, self.host, self.port)
            )
            
        except Exception as e:
            logger.error(f"Error starting servers: {e}", exc_info=True)

    async def _monitor_cluster(self):
        """Monitor cluster health and performance"""
        while True:
            try:
                for node_id in list(self.nodes.keys()):
                    # Update node metrics
                    metrics = await self._get_node_metrics(node_id)
                    self.performance_metrics[node_id] = metrics
                    
                    # Check node health
                    if metrics['cpu_usage'] > 90 or metrics['memory_usage'] > 90:
                        logger.warning(f"High resource usage on node {node_id}")
                        
                await self.broadcast_topology()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error monitoring cluster: {e}")
                await asyncio.sleep(5)

    async def _collect_metrics(self):
        """Collect detailed system metrics"""
        while True:
            try:
                metrics = await self._get_node_metrics()
                cluster_metrics = {
                    'nodes': metrics['nodes'],
                    'links': metrics['links'],
                    'cluster_stats': {
                        'total_nodes': len(self.nodes),
                        'active_nodes': len(self.connections),
                        'total_gpus': sum(node.gpu_count for node in self.nodes.values()),
                        'total_memory': sum(node.total_memory for node in self.nodes.values()),
                        'loaded_models': self._get_loaded_models()
                    }
                }
                
                if self.web_server:
                    await self.web_server.broadcast_metrics(cluster_metrics)
                    
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(1)

    async def handle_connection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming WebSocket connections"""
        node_id = None
        try:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get('type') == 'register':
                node_id = data['id']
                device_info = DeviceInfo(**data['device_info'])
                
                # Store connection and device info
                self.connections[node_id] = websocket
                self.nodes[node_id] = device_info
                
                logger.info(f"Node {node_id} connected")
                await self.broadcast_topology()
                
                try:
                    async for message in websocket:
                        await self.handle_message(node_id, message)
                except websockets.ConnectionClosed:
                    logger.info(f"Node {node_id} disconnected")
                finally:
                    if node_id in self.connections:
                        del self.connections[node_id]
                    if node_id in self.nodes:
                        del self.nodes[node_id]
                    await self.broadcast_topology()
                    
        except Exception as e:
            logger.error(f"Error handling connection: {e}", exc_info=True)
            if node_id:
                if node_id in self.connections:
                    del self.connections[node_id]
                if node_id in self.nodes:
                    del self.nodes[node_id]
                await self.broadcast_topology()

    async def handle_message(self, node_id: str, message: str):
        """Handle incoming messages from nodes"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'status_update':
                await self._handle_status_update(node_id, data)
            elif msg_type == 'model_update':
                await self._handle_model_update(node_id, data)
            elif msg_type == 'task_complete':
                await self._handle_task_complete(node_id, data)
            elif msg_type == 'resource_request':
                await self._handle_resource_request(node_id, data)
            elif msg_type == 'error':
                await self._handle_error(node_id, data)
                
        except Exception as e:
            logger.error(f"Error handling message from {node_id}: {e}")

    async def broadcast_topology(self):
        """Broadcast current topology to web interface"""
        try:
            topology = {
                'nodes': [
                    {
                        'id': node_id,
                        'info': asdict(info),
                        'role': 'master' if node_id == self.id else 'worker',
                        'metrics': self.performance_metrics.get(node_id, {}),
                        'models': self.model_registry.get(node_id, {}),
                        'status': 'active' if node_id in self.connections else 'disconnected'
                    }
                    for node_id, info in self.nodes.items()
                ],
                'links': [
                    {
                        'source': self.id,
                        'target': node_id,
                        'status': 'active' if node_id in self.connections else 'disconnected',
                        'traffic': self.performance_metrics.get(node_id, {}).get('network_traffic', 0)
                    }
                    for node_id in self.nodes.keys() if node_id != self.id
                ],
                'cluster_stats': {
                    'total_nodes': len(self.nodes),
                    'active_nodes': len(self.connections),
                    'total_gpus': sum(node.gpu_count for node in self.nodes.values()),
                    'total_memory': sum(node.total_memory for node in self.nodes.values()),
                    'loaded_models': self._get_loaded_models()
                }
            }
            
            if self.web_server:
                await self.web_server.broadcast_topology(topology)
            
        except Exception as e:
            logger.error(f"Error broadcasting topology: {e}", exc_info=True)

    def _get_loaded_models(self) -> Dict[str, List[str]]:
        """Get all loaded models across the cluster"""
        models = {}
        for node_id, node_models in self.model_registry.items():
            for model_name, model_info in node_models.items():
                if model_name not in models:
                    models[model_name] = []
                models[model_name].append(node_id)
        return models

    async def shutdown(self):
        """Shutdown the master node"""
        logger.info("Shutting down master node...")
        self.monitor_task.cancel()
        self.metrics_task.cancel()
        for connection in self.connections.values():
            await connection.close()
        self.connections.clear()
        self.nodes.clear()

    async def _get_node_metrics(self, node_id=None):
        """Get metrics from all connected nodes or a specific node"""
        if node_id:
            # Get metrics for specific node
            return {
                'cpu_usage': 0,  # Add actual CPU metrics collection
                'memory_usage': 0,  # Add actual memory metrics collection
                'last_seen': 0,  # Add timestamp
                'network_traffic': 0  # Add network metrics
            }
        
        # Get metrics for all nodes
        metrics = {
            'nodes': [],
            'links': []
        }
        
        for node_id, node_info in self.nodes.items():
            node_data = {
                'id': node_id,
                'role': 'master' if node_id == self.id else 'worker',
                'info': asdict(node_info)
            }
            metrics['nodes'].append(node_data)
            
            # Add links between master and workers
            if node_id != self.id:
                metrics['links'].append({
                    'source': self.id,
                    'target': node_id
                })
        
        return metrics

    async def _handle_status_update(self, node_id: str, data: dict):
        """Handle status update from node"""
        try:
            # Update node info
            if 'device_info' in data:
                self.nodes[node_id] = DeviceInfo(**data['device_info'])
            
            # Update performance metrics
            if 'metrics' in data:
                self.performance_metrics[node_id] = data['metrics']
            
            # Broadcast updated topology
            await self.broadcast_topology()
            
        except Exception as e:
            logger.error(f"Error handling status update from {node_id}: {e}")

    async def _handle_model_update(self, node_id: str, data: dict):
        """Handle model update from node"""
        try:
            if 'models' in data:
                self.model_registry[node_id] = data['models']
                await self.broadcast_topology()
        except Exception as e:
            logger.error(f"Error handling model update from {node_id}: {e}")

    async def _handle_task_complete(self, node_id: str, data: dict):
        """Handle task completion notification"""
        try:
            task_id = data.get('task_id')
            result = data.get('result')
            # Process completed task
            logger.info(f"Task {task_id} completed on node {node_id}")
        except Exception as e:
            logger.error(f"Error handling task completion from {node_id}: {e}")

    async def _handle_resource_request(self, node_id: str, data: dict):
        """Handle resource request from node"""
        try:
            resource_type = data.get('resource_type')
            amount = data.get('amount')
            # Process resource request
            logger.info(f"Resource request from {node_id}: {resource_type} = {amount}")
        except Exception as e:
            logger.error(f"Error handling resource request from {node_id}: {e}")

    async def _handle_error(self, node_id: str, data: dict):
        """Handle error report from node"""
        try:
            error_type = data.get('error_type')
            error_msg = data.get('error_msg')
            logger.error(f"Error reported from {node_id}: {error_type} - {error_msg}")
        except Exception as e:
            logger.error(f"Error handling error report from {node_id}: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--web-port', type=int, default=8080)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    args = parser.parse_args()

    master = MasterNode(port=args.port, web_port=args.web_port)
    
    # Start both services
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(master.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        loop.close()

if __name__ == "__main__":
    main()