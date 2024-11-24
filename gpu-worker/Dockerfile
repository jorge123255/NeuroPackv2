# Use the official CUDA image as the base
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Add Ollama installation
RUN curl https://ollama.ai/install.sh | sh

# Create Ollama directory
RUN mkdir -p /root/.ollama

# Set working directory
WORKDIR /app/NeuroPack

# Copy the entire repository
COPY . .

# Install requirements
RUN pip3 install --no-cache-dir -r gpu-worker/requirements.txt

# Install NeuroPack
RUN pip3 install -e .

# Create necessary directories
RUN mkdir -p logs config data cache model_cache

# Environment variables
ENV PYTHONPATH=/app/NeuroPack
ENV NODE_ROLE=gpu-worker
ENV NODE_PORT=8766
ENV CUDA_VISIBLE_DEVICES=all
ENV NVIDIA_VISIBLE_DEVICES=all

# Make start script executable
RUN chmod +x gpu-worker/start.sh

EXPOSE 8766 11434