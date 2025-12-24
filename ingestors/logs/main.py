import os
import json
import logging
from hanabi.utils.queue import DockerLogQueue
from api.app.services.log_storage import log_storage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LogsIngestor")

FALCO_CONTAINER = os.getenv("FALCO_CONTAINER", "falco")

def run():
    q = DockerLogQueue(container_name=FALCO_CONTAINER, max_queue_size=100000)
    q.start()
    try:
        while True:
            obj = q.get(timeout=1)
            if obj:
                log_storage.add_event(obj)
    except KeyboardInterrupt:
        pass
    finally:
        q.stop()

if __name__ == "__main__":
    run()

