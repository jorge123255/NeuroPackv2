#!/bin/bash

# Ensure NVIDIA drivers are loaded
nvidia-smi > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: NVIDIA drivers not detected"
    exit 1
fi

# Set default values for required environment variables
export MASTER_HOST=${MASTER_HOST:-"192.168.1.231"}
export MASTER_PORT=${MASTER_PORT:-"8765"}
export NODE_ID=${NODE_ID:-"gpu-worker"}
export PYTHONPATH=/app/NeuroPack:$PYTHONPATH

cd /app/NeuroPack

echo "Connecting to master at ${MASTER_HOST}:${MASTER_PORT}"

# Start Ollama in background
ollama serve &
sleep 2

# Start the worker node
python3 gpu-worker/laptop_node.py \
    --master ${MASTER_HOST} \
    --port ${MASTER_PORT} \
    --name ${NODE_ID}
