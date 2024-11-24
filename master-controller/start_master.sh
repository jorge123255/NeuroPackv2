#!/bin/bash

export PYTHONPATH=/app/NeuroPack:$PYTHONPATH
cd /app/NeuroPack/master-controller

echo "Starting NeuroPack Master Controller..."
echo "Web interface will be available at http://${HOST}:${WEB_PORT}"
echo "Node communication port: ${NODE_PORT}"

python3 run_master.py \
    --port ${NODE_PORT} \
    --web-port ${WEB_PORT} \
    --host ${HOST} 