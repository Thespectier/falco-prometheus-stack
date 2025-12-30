import os
import json
import logging
import time
from typing import List
from hanabi.utils.queue import DockerLogQueue
from api.app.services.log_storage import log_storage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LogsIngestor")

FALCO_CONTAINER = os.getenv("FALCO_CONTAINER", "43039infrasecurity-falco")
BATCH_SIZE = 5000
FLUSH_INTERVAL = 1.0  # seconds

def run():
    q = DockerLogQueue(container_name=FALCO_CONTAINER, max_queue_size=100000)
    q.start()
    
    buffer: List[dict] = []
    last_flush_time = time.time()
    
    logger.info(f"LogsIngestor started. Batch size: {BATCH_SIZE}, Flush interval: {FLUSH_INTERVAL}s")

    try:
        while True:
            try:
                # Use a small timeout to allow checking time-based flush
                obj = q.get(timeout=0.1)
                if obj:
                    buffer.append(obj)
            except Exception:
                # Queue empty or other error
                pass

            now = time.time()
            time_since_flush = now - last_flush_time
            
            # Check flush conditions
            if len(buffer) >= BATCH_SIZE or (len(buffer) > 0 and time_since_flush >= FLUSH_INTERVAL):
                try:
                    log_storage.add_event_batch(buffer)
                    # logger.info(f"Flushed {len(buffer)} events. Reason: {'Batch Size' if len(buffer) >= BATCH_SIZE else 'Time Limit'}")
                    buffer.clear()
                    last_flush_time = now
                except Exception as e:
                    logger.error(f"Failed to flush batch: {e}")
                    # In case of error, we might want to retry or clear to avoid getting stuck
                    # For now, we clear to keep processing new logs
                    buffer.clear() 
                    last_flush_time = now

    except KeyboardInterrupt:
        logger.info("Stopping LogsIngestor...")
        # Final flush
        if buffer:
            log_storage.add_event_batch(buffer)
    finally:
        q.stop()

if __name__ == "__main__":
    run()
