import asyncio
import signal
import logging
from master import MasterNode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    master = MasterNode(host="0.0.0.0", port=8765)
    
    try:
        logger.info("Starting NeuroPack Master Node")
        await master.start()
        await asyncio.Future()
    except Exception as e:
        logger.error(f"Error starting master node: {e}", exc_info=True)
        raise

async def shutdown(master):
    logger.info("Shutting down master node...")
    await master.shutdown()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.run(main()) 