import asyncio
import signal
import logging
from neuropack.distributed.master import MasterNode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    master = MasterNode()
    
    # Handle shutdown gracefully
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown(master)))
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown(master)))
    
    try:
        logger.info("Starting NeuroPack Master Node")
        await master.start()
    except Exception as e:
        logger.error(f"Error starting master node: {e}", exc_info=True)

async def shutdown(master):
    logger.info("Shutting down master node...")
    if hasattr(master, 'web_process'):
        master.web_process.terminate()
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.run(main()) 