#!/usr/bin/env python3
import asyncio
import argparse
from neuropack.distributed.master import MasterNode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--web-port', type=int, default=8080)
    parser.add_argument('--host', type=str, default='0.0.0.0')
    args = parser.parse_args()

    master = MasterNode(port=args.port, web_port=args.web_port)
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(master.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        loop.close()

if __name__ == "__main__":
    main() 