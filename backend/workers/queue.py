import asyncio
import logging

from services.pipeline import process_clip

logger = logging.getLogger(__name__)

processing_queue: asyncio.Queue = asyncio.Queue()


async def process_worker():
    while True:
        clip_id = await processing_queue.get()
        try:
            logger.info(f"Processing clip {clip_id}")
            await process_clip(clip_id)
            logger.info(f"Finished processing clip {clip_id}")
        except Exception:
            logger.exception(f"Error processing clip {clip_id}")
        finally:
            processing_queue.task_done()
