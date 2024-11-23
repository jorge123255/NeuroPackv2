import asyncio
import signal
import logging
from neuropack.distributed.master import MasterNode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    master = MasterNode()
    
    # Handle shutdown gracefully
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(master)))
    
    try:
        logger.info("Starting NeuroPack Master Node")
        await master.start()
        # Keep the server running
        await asyncio.Future()  # run forever
    except Exception as e:
        logger.error(f"Error starting master node: {e}", exc_info=True)
    finally:
        await shutdown(master)

async def shutdown(master):
    logger.info("Shutting down master node...")
    await master.shutdown()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.run(main()) 