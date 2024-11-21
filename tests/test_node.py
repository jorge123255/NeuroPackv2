import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from node import Node
import time

def test_resource_monitoring():
    node = Node()
    
    print("Initial resources:")
    node.print_info()
    
    print("\nMonitoring resources for 30 seconds...")
    for i in range(6):
        time.sleep(5)
        node.update_resources()
        print(f"\nUpdate {i+1}:")
        node.print_info()

if __name__ == "__main__":
    test_resource_monitoring()