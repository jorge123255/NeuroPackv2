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

1. Clone the repository:
```bash
git clone https://github.com/yourusername/neuropack.git
cd neuropack
```

2. Start the master node:
```bash
cd master-controller
docker-compose up -d
```

3. Set up worker nodes on each laptop:
```bash
python setup_laptop.py
```

4. Access the web interface:
- Local: http://localhost:8080
- Network: http://192.168.1.231:8080

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
git clone https://github.com/yourusername/NeuroPackv2.git
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
git clone https://github.com/yourusername/NeuroPackv2.git
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
