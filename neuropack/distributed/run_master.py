import asyncio
import logging
from pathlib import Path
import sys

# Add NeuroPack root to Python path
repo_root = Path(__file__).parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from neuropack.distributed.master import MasterNode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        master = MasterNode(port=8765)
        logger.info("Starting master node...")
        await master.start()
    except KeyboardInterrupt:
        logger.info("Shutting down master node...")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 