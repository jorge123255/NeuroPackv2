import subprocess
import sys
import platform
import os
import socket
from pathlib import Path

def get_laptop_info():
    """Get laptop information for node naming"""
    hostname = socket.gethostname()
    try:
        # Try to get a more user-friendly name
        if platform.system() == "Darwin":  # macOS
            friendly_name = subprocess.check_output(["scutil", "--get", "ComputerName"]).decode().strip()
        elif platform.system() == "Windows":
            friendly_name = os.environ.get("COMPUTERNAME", hostname)
        else:  # Linux
            friendly_name = hostname.split('.')[0]  # Remove domain if present
        return friendly_name
    except:
        return hostname

def setup_laptop():
    """Setup script for laptop nodes"""
    print("Setting up NeuroPack laptop node...")
    
    # Get laptop info
    laptop_name = get_laptop_info()
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    
    # Create venv directory
    venv_path = Path(__file__).parent / "venv"
    requirements_path = Path(__file__).parent / "laptop_requirements.txt"
    
    print(f"Creating virtual environment in {venv_path}...")
    try:
        subprocess.run([
            sys.executable,
            "-m",
            "venv",
            str(venv_path)
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error creating virtual environment: {e}")
        print("Try installing python3-venv with: sudo apt install python3-venv")
        sys.exit(1)
    
    # Get the pip path in the virtual environment
    if platform.system() == "Windows":
        pip_path = venv_path / "Scripts" / "pip"
        activate_path = venv_path / "Scripts" / "activate"
        python_path = venv_path / "Scripts" / "python"
    else:
        pip_path = venv_path / "bin" / "pip"
        activate_path = venv_path / "bin" / "activate"
        python_path = venv_path / "bin" / "python"
    
    print("Installing required packages...")
    try:
        subprocess.run([
            str(pip_path),
            "install",
            "-r",
            str(requirements_path)
        ], check=True)
        print("\nPackage installation successful!")
    except subprocess.CalledProcessError as e:
        print(f"\nError installing packages: {e}")
        sys.exit(1)
        
    # Create a convenience script for running the node
    if platform.system() != "Windows":
        run_script = Path(__file__).parent / "run_node.sh"
        repo_root = Path(__file__).parent.parent  # Path to NeuroPack root
        with open(run_script, "w") as f:
            f.write(f"""#!/bin/bash
source "{activate_path}"
export PYTHONPATH="{repo_root}:$PYTHONPATH"
python laptop_node.py --master "$1" --name "{laptop_name}"
""")
        run_script.chmod(0o755)  # Make executable
        
    print("\nSetup complete!")
    print("\nTo start the node, you can:")
    if platform.system() == "Windows":
        print(f'1. Run: "{activate_path}"')
        print(f'2. Then: python laptop_node.py --master MASTER_IP --name "{laptop_name}"')
    else:
        print(f'Simply run: ./run_node.sh MASTER_IP')
        print(f'(This will automatically use "{laptop_name}" as the node name)')
    
    print("\nExample:")
    if platform.system() == "Windows":
        print(f'python laptop_node.py --master 192.168.1.230 --name "{laptop_name}"')
    else:
        print(f'./run_node.sh 192.168.1.230')

if __name__ == "__main__":
    setup_laptop()