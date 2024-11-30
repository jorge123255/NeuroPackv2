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

    def setup_virtual_env(self):
        """Setup virtual environment and install dependencies"""
        logger.info("Setting up Python virtual environment...")
        try:
            venv_path = self.base_dir / 'venv'
            if not venv_path.exists():
                subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
                logger.info("Created virtual environment")

                # Install requirements
                pip_path = venv_path / 'bin' / 'pip' if platform.system() != 'Windows' else venv_path / 'Scripts' / 'pip'
                subprocess.run([str(pip_path), 'install', '-r', str(self.base_dir / 'requirements.txt')], check=True)
                logger.info("Installed dependencies")
            else:
                logger.info("Virtual environment already exists")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup virtual environment: {e}")
            return False

    def setup_worker(self):
        """Setup worker node configuration"""
        logger.info("Setting up worker node...")
        try:
            # Create necessary directories
            worker_dir = self.base_dir / 'worker'
            worker_dir.mkdir(exist_ok=True)
            (worker_dir / 'cache').mkdir(exist_ok=True)
            (worker_dir / 'logs').mkdir(exist_ok=True)
            
            # Create .env file
            env_file = self.base_dir / '.env'
            env_content = f"""
# Worker Configuration
MASTER_HOST={self.config['master_host']}
MASTER_PORT={self.config['master_port']}
NODE_ID=laptop-worker-1
NODE_PORT=8766
NODE_ROLE={self.config['node_role']}
MAX_MEMORY_PERCENT={self.config['max_memory_percent']}
LOG_LEVEL={self.config['log_level']}
LOG_FILE=worker/logs/worker.log
"""
            with open(env_file, 'w') as f:
                f.write(env_content.strip())
            
            logger.info("Created worker configuration")
            return True
        except Exception as e:
            logger.error(f"Failed to setup worker: {e}")
            return False

    def run(self):
        """Run the setup process"""
        try:
            # Check system requirements
            sys_info = self.check_system_requirements()
            
            # Setup virtual environment
            if not self.setup_virtual_env():
                raise Exception("Failed to setup virtual environment")
            
            # Setup worker configuration
            if not self.setup_worker():
                raise Exception("Failed to setup worker")
            
            logger.info("Setup completed successfully!")
            logger.info("\nTo start the worker, run:")
            if platform.system() != 'Windows':
                logger.info("source venv/bin/activate")
            else:
                logger.info(".\\venv\\Scripts\\activate")
            logger.info("python -m neuropack.distributed.node")
            
            return True
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

if __name__ == "__main__":
    setup = LaptopSetup()
    if setup.run():
        sys.exit(0)
    sys.exit(1)
