import asyncio
import logging
import json
import websockets
from pathlib import Path
import sys
import multiprocessing
import uvicorn
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import torch
import psutil
import GPUtil
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.tree import Tree
from rich.text import Text
from rich.style import Style
import aiohttp
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..distributed.node import Node, DeviceInfo
from ..web.server import TopologyServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MasterNode(Node):
    def __init__(self, host="0.0.0.0", port=8765):
        super().__init__(master_host=host, master_port=port)
        self.host = host
        self.port = port
        self.is_master = True
        self.web_server = None
        self.web_process = None
        self.connected_nodes = {}

    async def start(self):
        async with websockets.serve(self.handle_connection, self.host, self.port):
            self.web_server = TopologyServer()
            
            # Start web server in a separate process
            self.web_process = multiprocessing.Process(
                target=self.web_server.run
            )
            self.web_process.start()
            
            logging.info(f"Master node running on port {self.port}")
            logging.info(f"Web interface available at http://localhost:8080")
            
            # Keep the server running
            await asyncio.Future()  # run forever

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--web-port', type=int, default=8080)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    args = parser.parse_args()

    master = MasterNode(port=args.port, web_port=args.web_port)
    
    # Start both services
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(master.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        loop.close()

if __name__ == "__main__":
    main()