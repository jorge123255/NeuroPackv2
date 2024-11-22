# nodemanager/core/node.py
import uuid
import psutil
import torch
import platform
import socket
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List
import asyncio
import logging
from neuropack.core.distributed_manager import DistributedManager

logger = logging.getLogger(__name__)

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
    
    @classmethod
    def gather_info(cls) -> 'DeviceInfo':
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        
        gpu_info = []
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                gpu_info.append({
                    'name': torch.cuda.get_device_name(i),
                    'total_memory': torch.cuda.get_device_properties(i).total_memory,
                    'compute_capability': torch.cuda.get_device_capability(i)
                })
        
        return cls(
            cpu_count=psutil.cpu_count(),
            cpu_freq=psutil.cpu_freq().max,
            total_memory=psutil.virtual_memory().total,
            available_memory=psutil.virtual_memory().available,
            gpu_count=len(gpu_info),
            gpu_info=gpu_info,
            hostname=hostname,
            ip_address=ip,
            platform=platform.system()
        )

class Node:
    def __init__(self, master_host, master_port=8765):
        self.master_uri = f"ws://{master_host}:{master_port}"
        self.id = str(uuid.uuid4())
        self.device_info = DeviceInfo.gather_info()
        self.is_master = False
        self.connected_nodes: Dict[str, DeviceInfo] = {}
        
        if torch.cuda.is_available():
            self.gpu_manager = DistributedManager()
        else:
            self.gpu_manager = None
        
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'device_info': asdict(self.device_info),
            'is_master': self.is_master
        }
        
    async def start(self):
        """Start node operations"""
        if self.is_master:
            await self.start_master()
        else:
            await self.connect_to_master()
            
    async def start_master(self):
        """Start master node operations"""
        logger.info("Starting master node...")
        # Initialize master operations
        
    async def connect_to_master(self):
        """Connect to master node"""
        logger.info(f"Connecting to master at {self.master_uri}")
        # Connection logic