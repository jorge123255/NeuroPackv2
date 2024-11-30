# NeuroPackv2

A distributed model management system for efficient handling of large language models across multiple nodes.

## Features

- Distributed model management with automatic sharding
- Fault tolerance and automatic failover
- Load balancing and request routing
- Comprehensive metrics and monitoring
- Configuration management
- Support for both Hugging Face and Ollama models

## Version
2.0.0 - Latest update with distributed system enhancements

## Architecture

NeuroPack uses a simplified two-container architecture:

1. Master Node:
   - Web interface for topology and chat
   - Task distribution and management
   - Resource tracking and allocation
   - WebSocket communication hub

2. Worker Nodes:
   - LLM inference processing
   - Resource monitoring and reporting
   - Model weight caching
   - Task execution

## Prerequisites

- Python 3.8+
- Docker and Docker Compose
- NVIDIA GPU (optional but recommended)
- NVIDIA Container Toolkit (for GPU support)

## Quick Start

### Setting Up a Worker Node (Laptop)

1. Clone the repository:
```bash
git clone https://github.com/jorge123255/NeuroPackv2.git
cd NeuroPackv2
```

2. Run the setup script:
```bash
./setup_env.sh
```
This will:
- Create a Python virtual environment
- Install all required dependencies
- Configure your laptop as a worker node

3. Start the worker node:
```bash
./run_node.sh MASTER_IP
```
Replace `MASTER_IP` with your master node's IP address.

### Commands
Once the worker node is running, you can use these commands:
- `status` - Show node status (loaded models, connections, etc.)
- `quit` - Exit the worker node

## Development Setup

If you want to install the package for development:
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .
```

## Configuration

### Master Node
- Port 8765: WebSocket communication
- Port 8080: Web interface
- Environment variables:
  - NODE_ROLE=master
  - MAX_MEMORY_PERCENT=80
  - LOG_LEVEL=INFO

### Worker Node
- Environment variables:
  - MASTER_HOST=192.168.1.231
  - MASTER_PORT=8765
  - NODE_ROLE=worker
  - MAX_MEMORY_PERCENT=80
  - CUDA_VISIBLE_DEVICES=0

## Deployment Guide

### Prerequisites for Each Device

#### Master Controller (Any laptop/device):
- Docker and Docker Compose
- Stable network connection
- Fixed IP address recommended

#### GPU Workers (Laptops/devices with NVIDIA GPUs):
- Docker and Docker Compose
- NVIDIA Container Toolkit
- NVIDIA GPU with updated drivers
- Stable network connection

### Detailed Setup Instructions

#### 1. Master Controller Setup

```bash
# Clone the repository
git clone https://github.com/jorge123255/NeuroPackv2.git
cd NeuroPackv2

# Edit master-controller/docker-compose.yml
# Update the IP address (192.168.1.231) to match your network

# Start the master controller
cd master-controller
docker-compose up -d

# Verify it's running
docker ps
curl http://localhost:8080/health
```

#### 2. GPU Worker Setup

```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Clone the repository
git clone https://github.com/jorge123255/NeuroPackv2.git
cd NeuroPackv2

# Configure worker
# Edit gpu-worker/docker-compose.yml:
# - Update MASTER_HOST to your master controller's IP
# - Update the worker's IP address (192.168.1.232)
# - Adjust GPU-related environment variables if needed

# Start the GPU worker
cd gpu-worker
docker-compose up -d

# Verify it's running
docker ps
curl http://localhost:8766/health
```

### Network Configuration

1. All devices must be on the same network or have network connectivity
2. Update IP addresses in docker-compose files:
   - Master: Update `ipv4_address` in master-controller/docker-compose.yml
   - Workers: Update `ipv4_address` and `MASTER_HOST` in gpu-worker/docker-compose.yml

### System Management

#### Monitoring
- Master Dashboard: `http://master-ip:8080`
- Worker Metrics: `http://worker-ip:8766/metrics`
- Health Checks: `http://worker-ip:8766/health`

#### Common Commands
```bash
# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Update and rebuild
git pull
docker-compose down
docker-compose up -d --build
```

## Troubleshooting

### Worker Node Issues
- If the worker fails to connect, verify:
  - Master IP is correct
  - Master node is running
  - No firewall blocking port 8765
  - You're in the virtual environment (`source venv/bin/activate`)

### Virtual Environment
- If you see "command not found" errors, make sure you've:
  - Run `./setup_env.sh` first
  - Activated the environment: `source venv/bin/activate`

### Important Notes

1. Each GPU worker needs a unique `NODE_ID`
2. Adjust `MAX_MEMORY_PERCENT` based on GPU capacity
3. Start master controller before workers
4. For testing, master and worker can run on same GPU machine

### Troubleshooting

1. If worker can't connect to master:
   - Check IP addresses and network connectivity
   - Verify master controller is running
   - Check firewall settings

2. GPU issues:
   - Verify NVIDIA drivers: `nvidia-smi`
   - Check NVIDIA Container Toolkit: `docker run --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`
   - Ensure GPU is visible to Docker: `docker run --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`

3. Docker issues:
   - Check logs: `docker-compose logs`
   - Verify Docker daemon: `sudo systemctl status docker`
   - Restart Docker: `sudo systemctl restart docker`

## Non-Docker Worker Setup (Direct Installation)

For devices that prefer not to use Docker or need direct installation, follow these steps:

### Prerequisites for Direct Installation
- Python 3.8+
- pip
- For GPU support:
  - NVIDIA GPU
  - NVIDIA drivers
  - CUDA Toolkit 11.8+
  - cuDNN (for certain models)

### Installation Steps

1. **Set up Python environment**:
```bash
# Create and activate virtual environment
python -m venv neuropack-env
source neuropack-env/bin/activate  # Linux/Mac
# or
.\neuropack-env\Scripts\activate  # Windows

# Clone the repository
git clone https://github.com/jorge123255/NeuroPackv2.git
cd NeuroPackv2

# Install dependencies
pip install -r requirements.txt
```

2. **Install GPU Support (if using GPU)**:
```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For Ollama support (optional)
# Mac
curl https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download/windows
```

3. **Configure the Worker**:

Create a `.env` file in the project root:
```ini
# Worker Configuration
MASTER_HOST=192.168.1.231  # IP of your master controller
MASTER_PORT=8765
NODE_ID=laptop-worker-1    # Unique ID for this worker
NODE_PORT=8766
NODE_ROLE=worker
MAX_MEMORY_PERCENT=80
LOG_LEVEL=INFO

# GPU Configuration (if using GPU)
CUDA_VISIBLE_DEVICES=0     # Specify GPU indices to use
```

4. **Start the Worker**:
```bash
# Activate virtual environment if not already active
source neuropack-env/bin/activate  # Linux/Mac
# or
.\neuropack-env\Scripts\activate   # Windows

# Start the worker
python -m neuropack.distributed.node
```

### Managing the Worker

1. **Start/Stop**:
```bash
# Start worker (Linux/Mac)
./scripts/start_worker.sh

# Start worker (Windows)
scripts\start_worker.bat

# Stop worker
# Press Ctrl+C in the terminal window
```

2. **View Logs**:
```bash
# Logs are written to ./logs/worker.log
tail -f logs/worker.log  # Linux/Mac
# or
type logs\worker.log     # Windows
```

3. **Update Worker**:
```bash
# Pull latest changes
git pull

# Update dependencies
pip install -r requirements.txt

# Restart worker
```

### Troubleshooting Direct Installation

1. **Python/Package Issues**:
   - Verify Python version: `python --version`
   - Update pip: `python -m pip install --upgrade pip`
   - Clear pip cache: `pip cache purge`
   - Install in verbose mode: `pip install -v -r requirements.txt`

2. **GPU Issues**:
   - Check NVIDIA driver: `nvidia-smi`
   - Verify CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
   - Check GPU memory: `nvidia-smi -l 1`

3. **Connection Issues**:
   - Check network connectivity: `ping master-ip`
   - Verify ports are open: `nc -zv master-ip 8765`
   - Check firewall settings
   - Ensure master controller is running

4. **Common Errors**:
   - "CUDA not available": Install NVIDIA drivers and CUDA toolkit
   - "Connection refused": Check master controller IP and port
   - "Memory error": Adjust MAX_MEMORY_PERCENT in .env file
   - "Port in use": Change NODE_PORT in .env file

### Performance Optimization

1. **GPU Optimization**:
   - Set CUDA_VISIBLE_DEVICES to control GPU usage
   - Adjust MAX_MEMORY_PERCENT based on available GPU memory
   - Monitor GPU temperature and utilization

2. **CPU Optimization**:
   - Set number of worker threads in config
   - Monitor CPU usage and adjust batch sizes
   - Consider process priority settings

3. **Memory Management**:
   - Monitor RAM usage
   - Adjust model loading strategy
   - Implement model unloading when idle

## Monitoring

View logs:
```bash
# Master node logs
docker logs neuropack-master

# Worker node logs
docker logs neuropack-worker
```

Stop services:
```bash
# Master node
cd master-controller
docker-compose down

# Worker node
cd gpu-worker
docker-compose down
```

## Development

Run tests:
```bash
docker-compose -f docker-compose.test.yml up --build
```

## Security

- Node authentication (planned)
- Encrypted communication (planned)
- Resource access controls (planned)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
