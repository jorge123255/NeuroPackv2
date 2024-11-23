#!/bin/bash

# Activate virtual environment
source "$(dirname "$0")/venv/bin/activate"

# Set Python path to include NeuroPack root
export PYTHONPATH="$(dirname "$0")/..":$PYTHONPATH

# Check if master IP is provided
if [ -z "$1" ]; then
    echo "Error: Master IP address required"
    echo "Usage: $0 MASTER_IP [PORT]"
    exit 1
fi

# Get arguments
MASTER_IP=$1
PORT=${2:-8765}  # Use second argument as port, or default to 8765
HOSTNAME=$(hostname)

# Run the laptop node
python laptop_node.py --master "$MASTER_IP" --port "$PORT" --name "$HOSTNAME" 