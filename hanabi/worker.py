import os
import time
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Dict

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hanabi.utils.queue import DockerLogQueue
from hanabi.models.hbt import HBTModel
from hanabi.models.event_parser import EventParser

# Configuration
HBT_STORAGE_PATH = os.getenv("HBT_STORAGE_PATH", "/app/data/hbt")
FALCO_CONTAINER = os.getenv("FALCO_CONTAINER", "falco")
SAVE_INTERVAL_SECONDS = 30

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HanabiWorker")

class HanabiWorker:
    def __init__(self, container_name: str, storage_path: str):
        self.container_name = container_name
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.log_queue = DockerLogQueue(container_name=container_name)
        self.event_parser = EventParser()
        
        # In-memory models: container_id -> HBTModel
        # Note: In a real scenario, we might need to dynamically detect new containers.
        # For this prototype, we'll assume we are tracking the Falco container itself or 
        # extracting container IDs from logs.
        # But HBTModel takes a single container_id.
        # We need a way to manage multiple models.
        self.models: Dict[str, HBTModel] = {}
        
        self.running = False
        self.last_save_time = time.time()

    def get_or_create_model(self, container_id: str) -> HBTModel:
        if container_id not in self.models:
            logger.info(f"Creating new HBT model for container: {container_id}")
            self.models[container_id] = HBTModel(container_id)
        return self.models[container_id]

    def save_snapshots(self):
        """Save all HBT models to disk"""
        logger.info(f"Saving snapshots for {len(self.models)} containers...")
        for cid, model in self.models.items():
            try:
                data = model.get_model()
                file_path = self.storage_path / f"{cid}.json"
                
                # Write to temp file then rename for atomic update
                temp_path = file_path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    json.dump(data, f, ensure_ascii=False, default=str)
                temp_path.replace(file_path)
                
            except Exception as e:
                logger.error(f"Failed to save snapshot for {cid}: {e}")
        self.last_save_time = time.time()

    def start(self):
        self.running = True
        logger.info("Startup delay 30s before processing")
        time.sleep(30)
        self.log_queue.start()
        
        logger.info(f"Hanabi Worker started. Monitoring {self.container_name}")
        
        cnt = 0
        try:
            while self.running:
                # Non-blocking get or short timeout
                json_obj = self.log_queue.get(timeout=1)

                if json_obj:
                    cnt += 1
                    print("log:", cnt)  
                    self.process_event(json_obj)
                
                # Check if it's time to save
                if time.time() - self.last_save_time > SAVE_INTERVAL_SECONDS:
                    self.save_snapshots()
                    
        except KeyboardInterrupt:
            logger.info("Stopping worker...")
        finally:
            self.stop()

    def process_event(self, event: dict):
        try:
            
            output_fields = self.event_parser.extract_output_fields(event)
            container_id = output_fields.get("container.name") or "unknown"
            
            # Skip if no container info
            if not container_id or container_id == "unknown":
                return

            model = self.get_or_create_model(container_id)
            category = self.event_parser.categorize_event(event)
            
            if category == "process":
                model.add_process_event(output_fields)
            elif category == "network":
                model.add_network_event(output_fields)
            elif category == "file":
                model.add_file_event(output_fields)
                
        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def stop(self):
        self.running = False
        self.log_queue.stop()
        self.save_snapshots()
        logger.info("Worker stopped.")

def signal_handler(sig, frame):
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    worker = HanabiWorker(
        container_name=FALCO_CONTAINER, 
        storage_path=HBT_STORAGE_PATH
    )
    worker.start()
