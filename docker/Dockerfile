# Use the official Ubuntu image as the base
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# System packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    python3-distutils \
    python3-distutils-extra \
    build-essential \
    git \
    openssh-server \
    vim \
    nano \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Add Ollama installation
RUN curl https://ollama.ai/install.sh | sh

# Create Ollama directory
RUN mkdir -p /root/.ollama

# Add Ollama to PATH
ENV PATH="/usr/local/bin:${PATH}"

# SSH setup
RUN mkdir -p /var/run/sshd /etc/ssh/keys && \
    echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "HostKey /etc/ssh/keys/ssh_host_rsa_key" >> /etc/ssh/sshd_config && \
    echo "HostKey /etc/ssh/keys/ssh_host_ecdsa_key" >> /etc/ssh/sshd_config && \
    echo "HostKey /etc/ssh/keys/ssh_host_ed25519_key" >> /etc/ssh/sshd_config

# Set root password
RUN echo "root:password" | chpasswd

# Create app structure
WORKDIR /app

# Copy the entire project
COPY . /app/NeuroPack/

# Setup virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Upgrade pip first
RUN /app/venv/bin/pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA support
RUN /app/venv/bin/pip install --no-cache-dir \
    torch==2.2.2+cu118 \
    torchvision==0.17.2+cu118 \
    torchaudio==2.2.2 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# Install requirements and package
RUN /app/venv/bin/pip install --no-cache-dir -r /app/NeuroPack/requirements.txt && \
    cd /app/NeuroPack && \
    /app/venv/bin/pip install -e .

# Add CUDA environment variables
ENV PATH="/usr/local/cuda/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}"

# Add venv activation to bashrc
RUN echo "source /app/venv/bin/activate" >> /root/.bashrc

# Expose SSH port
EXPOSE 22

# Create necessary directories
RUN mkdir -p /app/NeuroPack/neuropack/distributed && \
    mkdir -p /app/NeuroPack/neuropack/web/static

# Create and populate the static directory with D3.js
RUN mkdir -p /app/NeuroPack/neuropack/web/static/js && \
    curl -L https://d3js.org/d3.v7.min.js -o /app/NeuroPack/neuropack/web/static/js/d3.min.js

# Copy web interface files
COPY ./neuropack/web/static /app/NeuroPack/neuropack/web/static/
COPY ./neuropack/web/server.py /app/NeuroPack/neuropack/web/
COPY ./neuropack/web/__init__.py /app/NeuroPack/neuropack/web/

# Copy distributed system files
COPY ./neuropack/distributed/master.py /app/NeuroPack/neuropack/distributed/
COPY ./neuropack/distributed/node.py /app/NeuroPack/neuropack/distributed/

# Add ports for node communication and web interface
EXPOSE 8765 8080 11434

# Copy startup script and make it executable
COPY docker/start_master.sh /app/start_master.sh
RUN chmod +x /app/start_master.sh

# Start SSH server and Ollama
CMD ["sh", "-c", "if [ ! -f /etc/ssh/keys/ssh_host_rsa_key ]; then ssh-keygen -f /etc/ssh/keys/ssh_host_rsa_key -N '' -t rsa && ssh-keygen -f /etc/ssh/keys/ssh_host_ecdsa_key -N '' -t ecdsa && ssh-keygen -f /etc/ssh/keys/ssh_host_ed25519_key -N '' -t ed25519; fi && /usr/sbin/sshd -D & ollama serve & /app/start_master.sh"]