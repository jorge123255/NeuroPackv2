import asyncio
import signal
from neuropack.distributed.master import MasterNode

async def main():
    master = MasterNode()
    
    # Handle shutdown gracefully
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(master)))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(master)))
    
    await master.start()

async def shutdown(master):
    # Cleanup code here
    if hasattr(master, 'web_process'):
        master.web_process.terminate()
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.run(main()) 