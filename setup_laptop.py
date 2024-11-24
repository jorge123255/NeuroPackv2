#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import platform
import psutil
import torch
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LaptopSetup:
    def __init__(self):
        self.base_dir = Path(__file__).parent.absolute()
        self.config = {
            'master_host': '192.168.1.231',
            'master_port': 8765,
            'node_role': 'worker',
            'max_memory_percent': 80,
            'log_level': 'INFO'
        }

    def check_system_requirements(self):
        """Check if system meets requirements"""
        logger.info("Checking system requirements...")
        
        # Check Python version
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            raise SystemError("Python 3.8+ is required")

        # Check GPU availability
        has_gpu = torch.cuda.is_available()
        if has_gpu:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
            logger.info(f"Found GPU: {gpu_name} with {gpu_memory:.1f}GB memory")
        else:
            logger.warning("No GPU detected - worker will run in CPU-only mode")

        # Check available memory
        total_memory = psutil.virtual_memory().total / (1024**3)  # Convert to GB
        logger.info(f"Total system memory: {total_memory:.1f}GB")

        return {
            'has_gpu': has_gpu,
            'gpu_info': {'name': gpu_name, 'memory': gpu_memory} if has_gpu else None,
            'total_memory': total_memory,
            'platform': platform.system()
        }

    def check_docker(self):
        """Check if Docker is installed and running"""
        try:
            subprocess.run(['docker', '--version'], check=True, capture_output=True)
            subprocess.run(['docker', 'info'], check=True, capture_output=True)
            logger.info("Docker is installed and running")
            return True
        except subprocess.CalledProcessError:
            logger.error("Docker is not installed or not running")
            return False
        except FileNotFoundError:
            logger.error("Docker is not installed")
            return False

    def create_docker_network(self):
        """Create Docker bridge network if it doesn't exist"""
        try:
            # Check if network exists
            result = subprocess.run(['docker', 'network', 'ls', '--format', '{{.Name}}'], 
                                 capture_output=True, text=True)
            if 'br0' not in result.stdout:
                # Create network
                subprocess.run(['docker', 'network', 'create', 
                             '--driver', 'bridge',
                             '--subnet', '192.168.1.0/24',
                             'br0'], check=True)
                logger.info("Created Docker network 'br0'")
            else:
                logger.info("Docker network 'br0' already exists")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create Docker network: {e}")
            raise

    def setup_worker(self):
        """Setup GPU worker node"""
        worker_dir = self.base_dir / 'gpu-worker'
        
        # Create directories if they don't exist
        worker_dir.mkdir(exist_ok=True)
        (worker_dir / 'cache').mkdir(exist_ok=True)
        
        # Write configuration
        config_path = worker_dir / 'config.json'
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
        
        logger.info("Starting GPU worker container...")
        try:
            subprocess.run(['docker-compose', 'up', '-d'], 
                         cwd=worker_dir, check=True)
            logger.info("GPU worker container started successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start GPU worker container: {e}")
            raise

    def run(self):
        """Run the setup process"""
        try:
            # Check requirements
            sys_info = self.check_system_requirements()
            
            # Check Docker
            if not self.check_docker():
                logger.error("Please install Docker and try again")
                return False
            
            # Create network
            self.create_docker_network()
            
            # Setup worker
            self.setup_worker()
            
            logger.info("Setup completed successfully!")
            logger.info("\nTo view logs:")
            logger.info("  docker logs neuropack-worker")
            logger.info("\nTo stop the worker:")
            logger.info("  cd gpu-worker && docker-compose down")
            
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

if __name__ == "__main__":
    setup = LaptopSetup()
    if setup.run():
        sys.exit(0)
    else:
        sys.exit(1)
