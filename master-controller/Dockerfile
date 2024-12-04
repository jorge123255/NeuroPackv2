FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire repository
COPY . /app/NeuroPack/

# Install NeuroPack and requirements
WORKDIR /app/NeuroPack
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install -e .

# Create necessary directories
RUN mkdir -p logs config data

# Environment variables
ENV PYTHONPATH=/app/NeuroPack
ENV NODE_ROLE=master
ENV LOG_LEVEL=INFO

# Make start script executable
RUN chmod +x master-controller/start_master.sh

EXPOSE 8765 8080

# Start command
ENTRYPOINT ["/bin/bash", "master-controller/start_master.sh"]