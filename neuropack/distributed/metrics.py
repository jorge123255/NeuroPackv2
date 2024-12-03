"""Metrics tracking for distributed model management."""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os
import logging
from prometheus_client import Counter, Histogram, Gauge, start_http_server

logger = logging.getLogger(__name__)

@dataclass
class ModelMetrics:
    model_name: str
    version: Optional[str]
    load_time: float
    memory_usage: float
    inference_count: int
    avg_inference_time: float
    error_count: int
    last_used: datetime
    node_distribution: Dict[str, int]  # node_id -> shard count

class MetricsManager:
    def __init__(self, metrics_port: int = 9090):
        self.metrics_port = metrics_port
        self.model_metrics: Dict[str, ModelMetrics] = {}
        
        # Prometheus metrics
        self.model_load_time = Histogram(
            'model_load_time_seconds',
            'Time taken to load models',
            ['model_name', 'version']
        )
        self.model_memory_usage = Gauge(
            'model_memory_usage_bytes',
            'Memory usage by model',
            ['model_name', 'version']
        )
        self.model_inference_count = Counter(
            'model_inference_total',
            'Total number of model inferences',
            ['model_name', 'version']
        )
        self.model_inference_time = Histogram(
            'model_inference_time_seconds',
            'Time taken for model inference',
            ['model_name', 'version']
        )
        self.model_error_count = Counter(
            'model_error_total',
            'Total number of model errors',
            ['model_name', 'version']
        )
        
        # Start Prometheus metrics server
        start_http_server(metrics_port)
        logger.info(f"Metrics server started on port {metrics_port}")

    def record_model_load(self, model_name: str, version: Optional[str], load_time: float, memory_usage: float, node_distribution: Dict[str, int]):
        """Record metrics for model loading"""
        self.model_metrics[model_name] = ModelMetrics(
            model_name=model_name,
            version=version,
            load_time=load_time,
            memory_usage=memory_usage,
            inference_count=0,
            avg_inference_time=0.0,
            error_count=0,
            last_used=datetime.now(),
            node_distribution=node_distribution
        )
        
        # Update Prometheus metrics
        self.model_load_time.labels(model_name=model_name, version=version or "latest").observe(load_time)
        self.model_memory_usage.labels(model_name=model_name, version=version or "latest").set(memory_usage)

    def record_inference(self, model_name: str, inference_time: float):
        """Record metrics for model inference"""
        if model_name in self.model_metrics:
            metrics = self.model_metrics[model_name]
            metrics.inference_count += 1
            metrics.avg_inference_time = (
                (metrics.avg_inference_time * (metrics.inference_count - 1) + inference_time)
                / metrics.inference_count
            )
            metrics.last_used = datetime.now()
            
            # Update Prometheus metrics
            self.model_inference_count.labels(
                model_name=model_name,
                version=metrics.version or "latest"
            ).inc()
            self.model_inference_time.labels(
                model_name=model_name,
                version=metrics.version or "latest"
            ).observe(inference_time)

    def record_error(self, model_name: str, error_type: str):
        """Record metrics for model errors"""
        if model_name in self.model_metrics:
            metrics = self.model_metrics[model_name]
            metrics.error_count += 1
            
            # Update Prometheus metrics
            self.model_error_count.labels(
                model_name=model_name,
                version=metrics.version or "latest"
            ).inc()

    def get_model_metrics(self, model_name: str) -> Optional[ModelMetrics]:
        """Get metrics for a specific model"""
        return self.model_metrics.get(model_name)

    def get_all_metrics(self) -> Dict[str, ModelMetrics]:
        """Get metrics for all models"""
        return self.model_metrics

    def export_metrics(self, export_path: str):
        """Export metrics to a JSON file"""
        metrics_data = {
            name: {
                "model_name": m.model_name,
                "version": m.version,
                "load_time": m.load_time,
                "memory_usage": m.memory_usage,
                "inference_count": m.inference_count,
                "avg_inference_time": m.avg_inference_time,
                "error_count": m.error_count,
                "last_used": m.last_used.isoformat(),
                "node_distribution": m.node_distribution
            }
            for name, m in self.model_metrics.items()
        }
        
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, 'w') as f:
            json.dump(metrics_data, f, indent=2)
