import subprocess
import sys
import platform
from pathlib import Path

def setup_laptop():
    """Setup script for laptop nodes"""
    print("Setting up NeuroPack laptop node...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    
    # Get requirements file path
    requirements_path = Path(__file__).parent / "laptop_requirements.txt"
    
    print("Installing required packages...")
    try:
        subprocess.run([
            sys.executable, 
            "-m", 
            "pip", 
            "install", 
            "-r", 
            str(requirements_path)
        ], check=True)
        print("\nPackage installation successful!")
    except subprocess.CalledProcessError as e:
        print(f"\nError installing packages: {e}")
        sys.exit(1)
        
    print("\nSetup complete! You can now run the laptop node with:")
    print("python laptop_node.py --master MASTER_IP --name YOUR_LAPTOP_NAME")

if __name__ == "__main__":
    setup_laptop() 