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
