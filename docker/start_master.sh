#!/bin/bash

# Activate virtual environment
source /app/venv/bin/activate

# Set Python path
export PYTHONPATH=/app/NeuroPack:$PYTHONPATH

# Set default ports if not provided
export NODE_PORT=${NODE_PORT:-8765}
export WEB_PORT=${WEB_PORT:-8080}

# Start SSH daemon in background
/usr/sbin/sshd

# Start the master node with web interface
echo "Starting NeuroPack Master Node..."
echo "Web interface will be available at http://192.168.1.230:${WEB_PORT}"
echo "Node communication port: ${NODE_PORT}"

cd /app/NeuroPack
# Install package in development mode
pip install -e .

# Run the master node
python -m neuropack.distributed.run_master \
    --port ${NODE_PORT} \
    --web-port ${WEB_PORT} \
    --host "0.0.0.0" 