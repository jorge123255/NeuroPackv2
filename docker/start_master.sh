#!/bin/bash

# Activate virtual environment
source /app/venv/bin/activate

# Set Python path
export PYTHONPATH=/app/NeuroPack:$PYTHONPATH

# Start master node
cd /app/NeuroPack
python3 neuropack/distributed/run_master.py 