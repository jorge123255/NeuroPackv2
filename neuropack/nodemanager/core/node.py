# nodemanager/core/node.py
import uuid
import psutil
import torch
import platform
import socket
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List

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
    def __init__(self, master_address: Optional[str] = None):
        self.id = str(uuid.uuid4())
        self.device_info = DeviceInfo.gather_info()
        self.master_address = master_address
        self.is_master = master_address is None
        self.connected_nodes: Dict[str, DeviceInfo] = {}
        
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'device_info': asdict(self.device_info),
            'is_master': self.is_master
        }