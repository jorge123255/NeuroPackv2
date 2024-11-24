#!/bin/bash

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install required packages
echo "Installing required packages..."
pip install psutil
pip install websockets
pip install numpy
pip install torch
pip install gputil

# Run setup script
echo "Running setup script..."
python setup_laptop.py

echo "Setup complete! To activate the environment in the future, run:"
echo "source venv/bin/activate"
