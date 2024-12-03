import asyncio
import json
import logging
import multiprocessing
from typing import Dict, Set, List, Optional
import websockets
from dataclasses import asdict, dataclass
from web.server import TopologyServer
from distributed.node import Node, DeviceInfo
import aiohttp
import time

logger = logging.getLogger(__name__)

@dataclass
class ModelInfo:
    name: str
    size: int
    loaded: bool
    shards: List[Dict]
    loading_progress: float = 0.0
    current_requests: int = 0
    total_tokens: int = 0
    avg_latency: float = 0.0

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
        
        # Model management attributes
        self.ollama_url = "http://localhost:11434/api"
        self.available_models: Dict[str, ModelInfo] = {}
        self.model_shards: Dict[str, Dict[str, List[int]]] = {}  # model -> {node_id: [layer_ids]}
        self.model_queue = asyncio.Queue()
        self.model_tasks = {}
        self.model_registry: Dict[str, Dict[str, ModelInfo]] = {}
        self.task_queue = asyncio.Queue()
        self.performance_metrics = {}

    async def start(self):
        """Start the master node and web interface"""
        logger.info(f"Starting master node on {self.host}:{self.port}")
        
        # Add self to nodes with master info
        self.nodes[self.id] = self.device_info
        
        # Create web server with correct parameter names
        self.web_server = TopologyServer(
            host=self.host,
            web_port=self.web_port,
            websocket_port=self.port
        )
        
        # Start monitoring tasks
        self.monitor_task = asyncio.create_task(self._monitor_cluster())
        self.metrics_task = asyncio.create_task(self._collect_metrics())
        self.model_monitor = asyncio.create_task(self._monitor_models())
        self.model_loader = asyncio.create_task(self._process_model_queue())
        
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
                changed = False
                for node_id in list(self.nodes.keys()):
                    # Update node metrics
                    metrics = await self._get_node_metrics(node_id)
                    if metrics != self.performance_metrics.get(node_id):
                        self.performance_metrics[node_id] = metrics
                        changed = True
                    
                    # Check node health
                    if metrics['cpu_usage'] > 90 or metrics['memory_usage'] > 90:
                        logger.warning(f"High resource usage on node {node_id}")
                
                if changed:
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
                    'links': metrics['links'],
                    'cluster_stats': {
                        'total_nodes': len(self.nodes),
                        'active_nodes': len(self.connections),
                        'total_gpus': sum(node.gpu_count for node in self.nodes.values()),
                        'total_memory': sum(node.total_memory for node in self.nodes.values()),
                        'loaded_models': self._get_loaded_models()
                    }
                }
                
                if self.web_server and cluster_metrics != getattr(self, '_last_metrics', None):
                    await self.web_server.broadcast_topology(cluster_metrics)
                    self._last_metrics = cluster_metrics
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(5)

    async def handle_connection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming WebSocket connections"""
        node_id = None
        try:
            message = await websocket.recv()
            data = json.loads(message)
            
            if data.get('type') != 'register':
                return
            
            node_id = data['id']
            node_info = data['device_info']
            
            # Required fields for DeviceInfo
            required_fields = {
                'cpu_count', 'cpu_freq', 'total_memory', 'available_memory',
                'gpu_count', 'gpu_info', 'hostname', 'ip_address', 'platform'
            }
            
            # Ensure all required fields are present
            if not all(field in node_info for field in required_fields):
                missing = required_fields - set(node_info.keys())
                raise ValueError(f"Missing required fields: {missing}")
            
            if node_id in self.connections:
                logger.warning(f"Node {node_id} already connected, closing old connection")
                await self.connections[node_id].close()
            
            # Create DeviceInfo instance with properly formatted data
            device_info = DeviceInfo(
                cpu_count=node_info['cpu_count'],
                cpu_freq=node_info['cpu_freq'],
                total_memory=node_info['total_memory'],
                available_memory=node_info['available_memory'],
                gpu_count=node_info['gpu_count'],
                gpu_info=node_info['gpu_info'],
                hostname=node_info['hostname'],
                ip_address=node_info['ip_address'],
                platform=node_info['platform'],
                role=node_info.get('role', 'worker')
            )
            
            self.nodes[node_id] = device_info
            self.connections[node_id] = websocket
            gpu_count = len(node_info.get('gpu_info', []))
            logger.info(f"Node {node_id} registered with {gpu_count} GPUs")
            
            # Send registration acknowledgment
            await websocket.send(json.dumps({
                'type': 'register_ack',
                'id': node_id
            }))
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._send_heartbeat(node_id, websocket))
            
            try:
                while True:
                    try:
                        message = await websocket.recv()
                        await self._handle_node_message(node_id, json.loads(message))
                    except websockets.ConnectionClosed:
                        logger.warning(f"Connection closed for node {node_id}")
                        break
                    except json.JSONDecodeError:
                        logger.error("Invalid message format")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        # Don't break on message handling errors
                        
            finally:
                heartbeat_task.cancel()
                if node_id in self.nodes:
                    del self.nodes[node_id]
                if node_id in self.connections:
                    del self.connections[node_id]
                    
        except Exception as e:
            logger.error(f"Connection error: {e}")

    async def _send_heartbeat(self, node_id: str, websocket: websockets.WebSocketServerProtocol):
        """Send periodic heartbeat to node"""
        try:
            while True:
                try:
                    await websocket.send(json.dumps({
                        'type': 'heartbeat',
                        'timestamp': time.time()
                    }))
                    await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                except websockets.ConnectionClosed:
                    break
                except Exception as e:
                    logger.error(f"Error sending heartbeat to {node_id}: {e}")
                    break
        except asyncio.CancelledError:
            pass

    async def _handle_node_message(self, node_id: str, message):
        """Handle messages from worker nodes"""
        try:
            # Handle both string and dict messages
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON message from {node_id}: {message}")
                    logger.error(f"JSON decode error: {e}")
                    return
            elif isinstance(message, dict):
                data = message
            else:
                logger.error(f"Received invalid message type from {node_id}: {type(message)}")
                return
            
            msg_type = data.get('type')
            
            if msg_type == 'heartbeat_response':
                # Update last seen timestamp
                if node_id in self.nodes:
                    self.nodes[node_id].last_seen = asyncio.get_event_loop().time()
            elif msg_type == 'status_update':
                # Handle status updates without closing connection
                if node_id in self.nodes and 'device_info' in data:
                    self.nodes[node_id] = DeviceInfo(**data['device_info'])
                    await self.broadcast_topology()
            elif msg_type == 'metrics_update':
                # Update node metrics
                self.performance_metrics[node_id] = data.get('metrics', {})
                await self.broadcast_topology()
            elif msg_type == 'model_update':
                # Update model registry
                self.model_registry[node_id] = data.get('models', {})
                await self.broadcast_topology()
                
        except Exception as e:
            logger.error(f"Error handling node message: {e}")
            # Don't close connection on error

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
            
            logger.info(f"Broadcasting topology - Nodes: {len(topology['nodes'])}, Links: {len(topology['links'])}")
            logger.debug(f"Topology data: {json.dumps(topology, indent=2)}")
            
            if self.web_server:
                await self.web_server.broadcast_topology(topology)
            else:
                logger.warning("Web server not initialized, cannot broadcast topology")
            
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

    async def _monitor_models(self):
        """Monitor model status and performance"""
        while True:
            try:
                for model_name, info in self.available_models.items():
                    if info.loaded:
                        # Update model metrics
                        metrics = await self._get_model_metrics(model_name)
                        info.current_requests = metrics.get('current_requests', 0)
                        info.total_tokens = metrics.get('total_tokens', 0)
                        info.avg_latency = metrics.get('avg_latency', 0.0)

                await self.broadcast_topology()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error monitoring models: {e}")
                await asyncio.sleep(5)

    async def _process_model_queue(self):
        """Process queued model loading tasks"""
        while True:
            try:
                task = await self.model_queue.get()
                model_name = task['model']
                node_id = task['node_id']

                if task.get('full_model'):
                    success = await self._load_model_on_node(node_id, model_name)
                else:
                    success = await self._load_model_shard(
                        node_id, 
                        model_name, 
                        task['shard'], 
                        task['layers']
                    )

                if success:
                    logger.info(f"Successfully loaded {model_name} on {node_id}")
                    await self.broadcast_topology()

            except Exception as e:
                logger.error(f"Error processing model queue: {e}")
            finally:
                self.model_queue.task_done()

    async def load_model(self, model_name: str, distributed: bool = True) -> bool:
        """Load a model with optional distribution"""
        try:
            model_info = await self._get_model_info(model_name)
            if not model_info:
                return False

            available_gpus = self._get_available_gpus()
            if not available_gpus:
                logger.error("No GPUs available for model loading")
                return False

            if distributed and len(available_gpus) > 1:
                shards = self._calculate_model_shards(model_info, available_gpus)
                for shard in shards:
                    await self.model_queue.put({
                        'model': model_name,
                        'shard': shard['shard_id'],
                        'node_id': shard['node_id'],
                        'layers': shard['layers']
                    })
                
                self.model_shards[model_name] = {
                    shard['node_id']: shard['layers'] 
                    for shard in shards
                }
            else:
                best_node = max(available_gpus.items(), key=lambda x: x[1]['free_memory'])[0]
                await self.model_queue.put({
                    'model': model_name,
                    'node_id': best_node,
                    'full_model': True
                })

            return True
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            return False

    async def _get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get model information from Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/show/{model_name}") as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return None

    def _calculate_model_shards(self, model_info: Dict, available_gpus: Dict) -> List[Dict]:
        """Calculate optimal model sharding across available GPUs"""
        total_memory = model_info.get('size', 0)
        total_layers = model_info.get('num_layers', 1)
        
        sorted_gpus = sorted(
            available_gpus.items(), 
            key=lambda x: x[1]['free_memory'], 
            reverse=True
        )

        shards = []
        layers_assigned = 0
        
        for i, (node_id, gpu_info) in enumerate(sorted_gpus):
            if layers_assigned >= total_layers:
                break
                
            gpu_memory = gpu_info['free_memory']
            layers_for_gpu = int((gpu_memory / total_memory) * total_layers)
            
            if i == len(sorted_gpus) - 1:
                layers_for_gpu = total_layers - layers_assigned
            
            if layers_for_gpu > 0:
                shards.append({
                    'node_id': node_id,
                    'shard_id': i,
                    'layers': list(range(layers_assigned, layers_assigned + layers_for_gpu)),
                    'memory': (layers_for_gpu / total_layers) * total_memory
                })
                layers_assigned += layers_for_gpu

        return shards

    async def handle_inference_request(self, prompt: str, model_name: str):
        """Handle incoming inference requests with load balancing"""
        try:
            # Find nodes with model loaded
            available_nodes = [
                node_id for node_id, node in self.nodes.items()
                if model_name in node.device_info.loaded_models
            ]
            
            if not available_nodes:
                # Model not loaded anywhere, select best nodes for loading
                gpu_nodes = sorted(
                    self.nodes.items(),
                    key=lambda x: (
                        x[1].device_info.available_memory,
                        -x[1].device_info.current_tasks
                    ),
                    reverse=True
                )
                
                if not gpu_nodes:
                    raise Exception("No GPU nodes available")
                    
                # Load model with sharding if needed
                model_size = await self._get_model_size(model_name)
                if model_size > gpu_nodes[0][1].device_info.available_memory:
                    # Need to shard across multiple GPUs
                    shards = self._calculate_model_shards(
                        model_size,
                        {node_id: node for node_id, node in gpu_nodes}
                    )
                    
                    for shard in shards:
                        await self._load_model_shard(
                            model_name,
                            shard['node_id'],
                            shard['layers']
                        )
                else:
                    # Load on single GPU
                    best_node = gpu_nodes[0][0]
                    await self._load_model(model_name, best_node)
                    
            # Now handle the actual inference
            if len(available_nodes) > 1:
                # Distributed inference across shards
                return await self._distributed_inference(prompt, model_name, available_nodes)
            else:
                # Single node inference
                node_id = available_nodes[0]
                return await self._single_node_inference(prompt, model_name, node_id)
                
        except Exception as e:
            logger.error(f"Inference error: {e}")
            raise

    async def _distributed_inference(self, prompt: str, model_name: str, nodes: List[str]):
        """Handle distributed inference across multiple nodes"""
        try:
            # Split computation across nodes
            futures = []
            for node_id in nodes:
                ws = self.connections[node_id]
                request = {
                    'type': 'inference',
                    'model': model_name,
                    'prompt': prompt,
                    'is_distributed': True
                }
                futures.append(ws.send_json(request))
                
            # Gather results
            responses = await asyncio.gather(*futures)
            
            # Combine results (implementation depends on model architecture)
            return self._combine_distributed_results(responses)
            
        except Exception as e:
            logger.error(f"Distributed inference error: {e}")
            raise

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