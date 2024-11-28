"""Configuration management for the distributed model system."""
from dataclasses import dataclass
from typing import Dict, List, Optional
import yaml
import logging
import os

logger = logging.getLogger(__name__)

@dataclass
class NodeConfig:
    """Configuration for a single node in the system."""
    node_id: str
    host: str
    port: int
    gpu_memory: int  # Available GPU memory in MB
    max_models: int  # Maximum number of models that can be loaded simultaneously
    health_check_endpoint: str = "/health"

@dataclass
class ModelConfig:
    """Configuration for a model that can be served."""
    model_name: str
    model_type: str  # "huggingface" or "ollama"
    min_gpu_memory: int  # Minimum required GPU memory in MB
    max_batch_size: int
    timeout: int  # Maximum time in seconds for model inference
    version: str
    config: Dict  # Model-specific configuration

@dataclass
class SystemConfig:
    """System-wide configuration settings."""
    health_check_interval: int = 30  # Seconds between health checks
    request_timeout: int = 300  # Maximum time to keep request records
    load_balancing_strategy: str = "least_loaded"  # "least_loaded", "round_robin", or "random"
    retry_attempts: int = 3  # Number of retries before failover
    timeout: int = 10  # Default timeout for operations in seconds
    metrics_port: int = 9090  # Port for Prometheus metrics

class ConfigManager:
    """Manages configuration for the distributed model system."""
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.nodes: Dict[str, NodeConfig] = {}
        self.models: Dict[str, ModelConfig] = {}
        self.system = SystemConfig()
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found at {self.config_path}")
                return

            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Load system configuration
            if 'system' in config:
                system_config = config['system']
                self.system = SystemConfig(
                    health_check_interval=system_config.get('health_check_interval', 30),
                    request_timeout=system_config.get('request_timeout', 300),
                    load_balancing_strategy=system_config.get('load_balancing_strategy', 'least_loaded'),
                    retry_attempts=system_config.get('retry_attempts', 3),
                    timeout=system_config.get('timeout', 10),
                    metrics_port=system_config.get('metrics_port', 9090)
                )

            # Load node configurations
            if 'nodes' in config:
                for node_data in config['nodes']:
                    node_config = NodeConfig(
                        node_id=node_data['node_id'],
                        host=node_data['host'],
                        port=node_data['port'],
                        gpu_memory=node_data['gpu_memory'],
                        max_models=node_data['max_models'],
                        health_check_endpoint=node_data.get('health_check_endpoint', '/health')
                    )
                    self.nodes[node_config.node_id] = node_config

            # Load model configurations
            if 'models' in config:
                for model_data in config['models']:
                    model_config = ModelConfig(
                        model_name=model_data['model_name'],
                        model_type=model_data['model_type'],
                        min_gpu_memory=model_data['min_gpu_memory'],
                        max_batch_size=model_data['max_batch_size'],
                        timeout=model_data['timeout'],
                        version=model_data['version'],
                        config=model_data.get('config', {})
                    )
                    self.models[model_config.model_name] = model_config

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def save_config(self):
        """Save current configuration to YAML file."""
        try:
            config = {
                'system': {
                    'health_check_interval': self.system.health_check_interval,
                    'request_timeout': self.system.request_timeout,
                    'load_balancing_strategy': self.system.load_balancing_strategy,
                    'retry_attempts': self.system.retry_attempts,
                    'timeout': self.system.timeout,
                    'metrics_port': self.system.metrics_port
                },
                'nodes': [
                    {
                        'node_id': node.node_id,
                        'host': node.host,
                        'port': node.port,
                        'gpu_memory': node.gpu_memory,
                        'max_models': node.max_models,
                        'health_check_endpoint': node.health_check_endpoint
                    }
                    for node in self.nodes.values()
                ],
                'models': [
                    {
                        'model_name': model.model_name,
                        'model_type': model.model_type,
                        'min_gpu_memory': model.min_gpu_memory,
                        'max_batch_size': model.max_batch_size,
                        'timeout': model.timeout,
                        'version': model.version,
                        'config': model.config
                    }
                    for model in self.models.values()
                ]
            }

            with open(self.config_path, 'w') as f:
                yaml.safe_dump(config, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise

    def get_node_config(self, node_id: str) -> Optional[NodeConfig]:
        """Get configuration for a specific node."""
        return self.nodes.get(node_id)

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model."""
        return self.models.get(model_name)

    def add_node(self, node_config: NodeConfig):
        """Add or update a node configuration."""
        self.nodes[node_config.node_id] = node_config
        self.save_config()

    def remove_node(self, node_id: str):
        """Remove a node configuration."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.save_config()

    def add_model(self, model_config: ModelConfig):
        """Add or update a model configuration."""
        self.models[model_config.model_name] = model_config
        self.save_config()

    def remove_model(self, model_name: str):
        """Remove a model configuration."""
        if model_name in self.models:
            del self.models[model_name]
            self.save_config()

    def get_models_for_node(self, node_id: str) -> List[str]:
        """Get list of models that can run on a specific node."""
        node_config = self.get_node_config(node_id)
        if not node_config:
            return []

        return [
            model.model_name for model in self.models.values()
            if model.min_gpu_memory <= node_config.gpu_memory
        ]

    def validate_config(self) -> bool:
        """Validate the current configuration."""
        try:
            # Check system config
            if self.system.health_check_interval <= 0:
                logger.error("Health check interval must be positive")
                return False

            if self.system.request_timeout <= 0:
                logger.error("Request timeout must be positive")
                return False

            if self.system.load_balancing_strategy not in ["least_loaded", "round_robin", "random"]:
                logger.error("Invalid load balancing strategy")
                return False

            # Check node configs
            for node in self.nodes.values():
                if node.gpu_memory <= 0:
                    logger.error(f"Invalid GPU memory for node {node.node_id}")
                    return False
                if node.max_models <= 0:
                    logger.error(f"Invalid max models for node {node.node_id}")
                    return False

            # Check model configs
            for model in self.models.values():
                if model.min_gpu_memory <= 0:
                    logger.error(f"Invalid min GPU memory for model {model.model_name}")
                    return False
                if model.max_batch_size <= 0:
                    logger.error(f"Invalid max batch size for model {model.model_name}")
                    return False
                if model.timeout <= 0:
                    logger.error(f"Invalid timeout for model {model.model_name}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False
