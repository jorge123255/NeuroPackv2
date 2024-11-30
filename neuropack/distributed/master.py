import asyncio
import json
import logging
import multiprocessing
from typing import Dict, Set, List, Optional
import websockets
from dataclasses import asdict, dataclass, field, fields
from neuropack.web.server import TopologyServer
from neuropack.distributed.node import Node
import aiohttp
import uuid
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

@dataclass
class DeviceInfo:
    cpu_count: int
    cpu_freq: float
    total_memory: int
    available_memory: int
    gpu_count: int
    gpu_info: List[Dict]
    hostname: str
    ip_address: str
    platform: str
    loaded_models: Dict[str, Dict] = field(default_factory=dict)
    supported_models: List[str] = field(default_factory=list)
    last_heartbeat: float = 0.0
    websocket: websockets.WebSocketServerProtocol = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'DeviceInfo':
        # Remove any unexpected fields from the data
        expected_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in expected_fields}
        return cls(**filtered_data)

    def update_device_info(self, device_info: Dict):
        for key, value in device_info.items():
            if hasattr(self, key):
                setattr(self, key, value)

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
        self.heartbeat_timeout = 30  # seconds
        self.heartbeat_interval = 10  # seconds

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
        self.model_monitor = asyncio.create_task(self._monitor_models())
        self.model_loader = asyncio.create_task(self._process_model_queue())
        self.node_check_task = asyncio.create_task(self._check_nodes())
        
        try:
            await asyncio.gather(
                self.web_server.start(),
                websockets.serve(self.handle_websocket, self.host, self.port)
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

    async def handle_websocket(self, websocket, path):
        """Handle websocket connection"""
        node_id = None
        try:
            async for message in websocket:
                logger.debug(f"Received raw message type: {type(message)}")
                logger.debug(f"Raw message content: {message}")
                
                if node_id is None:
                    # First message should be registration
                    try:
                        if isinstance(message, str):
                            data = json.loads(message)
                        else:
                            data = message
                            
                        if data.get('type') != 'register':
                            logger.error("First message must be registration")
                            return
                            
                        node_id = data.get('id')
                        if not node_id:
                            logger.error("Registration missing node id")
                            return
                            
                        # Store connection
                        self.connections[node_id] = websocket
                        
                        # Handle registration message
                        await self.handle_node_message(node_id, message)
                        
                    except Exception as e:
                        logger.error(f"Error processing registration: {e}")
                        logger.error(f"Registration message was: {message}")
                        return
                else:
                    # Handle subsequent messages
                    await self.handle_node_message(node_id, message)
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Node {node_id} disconnected")
            
        finally:
            # Clean up connection
            if node_id:
                if node_id in self.connections:
                    del self.connections[node_id]
                if node_id in self.nodes:
                    del self.nodes[node_id]
                await self.broadcast_topology()

    async def handle_node_message(self, node_id: str, message):
        """Handle incoming messages from nodes"""
        try:
            logger.debug(f"Handling message of type {type(message)} from node {node_id}")
            
            # Handle both string and dict messages
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                    logger.debug("Successfully parsed JSON string")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON message from {node_id}: {message}")
                    logger.error(f"JSON decode error: {e}")
                    return
            elif isinstance(message, dict):
                logger.debug("Message is already a dict, using as is")
                data = message
            else:
                logger.error(f"Received invalid message type from {node_id}: {type(message)}")
                return

            msg_type = data.get('type')
            if not msg_type:
                logger.error(f"Message from {node_id} missing 'type' field: {data}")
                return

            logger.debug(f"Processing message type {msg_type} from {node_id}")
            
            if msg_type == 'register':
                # Handle registration message
                device_info = data.get('device_info', {})
                if not isinstance(device_info, dict):
                    logger.error(f"Invalid device_info format from {node_id}: {device_info}")
                    return
                    
                # Filter device info to only include valid fields
                valid_fields = {f.name for f in fields(DeviceInfo)}
                device_info = {k: v for k, v in device_info.items() 
                             if k in valid_fields}
                
                try:
                    device_info_obj = DeviceInfo.from_dict(device_info)
                    self.nodes[node_id] = device_info_obj
                    logger.info(f"Node {node_id} registered with {device_info_obj.gpu_count} GPUs")
                    await self.broadcast_topology()
                except Exception as e:
                    logger.error(f"Error registering node {node_id}: {e}")
                    logger.error(f"Device info was: {device_info}")
                    
            elif msg_type == 'status_update':
                if node_id not in self.nodes:
                    logger.warning(f"Status update from unregistered node: {node_id}")
                    return
                    
                device_info = data.get('device_info', {})
                if not isinstance(device_info, dict):
                    logger.error(f"Invalid device_info in status update from {node_id}: {device_info}")
                    return
                    
                # Filter and update device info
                valid_fields = {f.name for f in fields(DeviceInfo)}
                device_info = {k: v for k, v in device_info.items() 
                             if k in valid_fields}
                
                try:
                    self.nodes[node_id].update_device_info(device_info)
                    logger.debug(f"Updated device info for node {node_id}")
                except Exception as e:
                    logger.error(f"Error updating device info for {node_id}: {e}")
                    logger.error(f"Device info was: {device_info}")
                    
            elif msg_type == 'heartbeat_response':
                if node_id in self.nodes:
                    self.nodes[node_id].last_heartbeat = time.time()
                    logger.debug(f"Updated heartbeat for node {node_id}")
                else:
                    logger.warning(f"Heartbeat from unregistered node: {node_id}")
                    
            elif msg_type == 'error':
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"Error from node {node_id}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error handling node message: {e}")
            logger.error(f"Message was: {message}")
            logger.error("Stack trace:", exc_info=True)

    async def _send_message(self, websocket, message):
        """Send a message to a node"""
        try:
            if not websocket:
                logger.warning("No websocket connection available")
                return
                
            if isinstance(message, str):
                await websocket.send(message)
            else:
                try:
                    json_message = json.dumps(message)
                    await websocket.send(json_message)
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
                    logger.error(f"Message was: {message}")
                    
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            # Remove node if we can't send messages to it
            for node_id, node in list(self.nodes.items()):
                if node.websocket == websocket:
                    logger.warning(f"Removing node {node_id} due to connection error")
                    del self.nodes[node_id]
                    break

    async def _check_nodes(self):
        """Periodically check node status and send heartbeats"""
        while True:
            try:
                current_time = time.time()
                for node_id, node in list(self.nodes.items()):
                    # Remove nodes that haven't responded to heartbeat
                    if current_time - node.last_heartbeat > self.heartbeat_timeout:
                        logger.warning(f"Node {node_id} timed out, removing")
                        del self.nodes[node_id]
                        continue
                        
                    # Send heartbeat to active nodes
                    try:
                        message = {
                            'type': 'heartbeat',
                            'id': 'master'
                        }
                        await self._send_message(node.websocket, message)
                    except Exception as e:
                        logger.error(f"Failed to send heartbeat to node {node_id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error in node check loop: {e}")
                
            await asyncio.sleep(self.heartbeat_interval)

    async def broadcast_topology(self):
        """Broadcast current topology to web interface"""
        try:
            nodes_info = []
            for node_id, info in self.nodes.items():
                node_data = {
                    'id': node_id,
                    'device_info': asdict(info),
                    'role': 'master' if node_id == self.id else 'worker',
                    'metrics': self.performance_metrics.get(node_id, {}),
                    'models': self.model_registry.get(node_id, {}),
                    'status': 'active' if node_id in self.connections else 'disconnected'
                }
                nodes_info.append(node_data)
                
            # Calculate links between nodes
            links = []
            for node_id in self.nodes:
                if node_id != self.id:  # Not master
                    links.append({
                        'source': self.id,
                        'target': node_id,
                        'type': 'control'
                    })
                    
            topology = {
                'nodes': nodes_info,
                'links': links
            }
            
            logger.info(f"Broadcasting topology - Nodes: {len(nodes_info)}, Links: {len(links)}")
            
            # Convert topology to JSON string before sending
            try:
                topology_json = json.dumps(topology)
                await self.web_server.broadcast_topology(topology_json)
            except Exception as e:
                logger.error(f"Error serializing topology: {e}")
                return
                
        except Exception as e:
            logger.error(f"Error broadcasting topology: {e}")

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

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--web-port', type=int, default=8080)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    args = parser.parse_args()

    master = MasterNode(port=args.port, web_port=args.web_port, host=args.host)
    
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