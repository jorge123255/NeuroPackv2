#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install required packages from setup.py
echo "Installing package in development mode..."
pip install -e .

# Run laptop setup script
echo "Running laptop setup script..."
python Devices/setup_laptop.py

echo "Setup complete!"
echo "To activate the environment in the future, run: source venv/bin/activate"
echo "To start the worker node, run: ./run_node.sh MASTER_IP"
