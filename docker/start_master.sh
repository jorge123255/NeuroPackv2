#!/bin/bash

# Start SSH daemon in background
/usr/sbin/sshd

# Start Ollama service
echo "Starting Ollama service..."
ollama serve &

# Wait for Ollama to start
echo "Waiting for Ollama to initialize..."
sleep 5

# Activate virtual environment
source /app/venv/bin/activate

# Set Python path
export PYTHONPATH=/app/NeuroPack:$PYTHONPATH

# Set default ports if not provided
export NODE_PORT=${NODE_PORT:-8765}
export WEB_PORT=${WEB_PORT:-8080}

# Start the master node with web interface
echo "Starting NeuroPack Master Node..."
echo "Web interface will be available at http://192.168.1.230:${WEB_PORT}"
echo "Node communication port: ${NODE_PORT}"
echo "Ollama API available at port 11434"

cd /app/NeuroPack
# Install package in development mode
pip install -e .

# Run the master node
python3 -m neuropack.distributed.run_master \
    --port ${NODE_PORT} \
    --web-port ${WEB_PORT} \
    --host "0.0.0.0" 