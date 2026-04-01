import threading
import time
import atexit
import logging
from fastapi import FastAPI, Body
from typing import Dict, Any, List
import os
from api.app.services.log_storage import log_storage

logger = logging.getLogger("AlertsIngestor")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Alerts Ingestor", version="0.1.0")

class AlertsBuffer:
    def __init__(self, batch_size: int = 1000, flush_interval: int = 10):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.running = True
        self.worker_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.worker_thread.start()
        atexit.register(self.stop)

    def add_alert(self, payload: Dict[str, Any]):
        with self.lock:
            self.buffer.append(payload)

    def _flush_loop(self):
        while self.running:
            time.sleep(self.flush_interval)
            self.flush()

    def flush(self):
        with self.lock:
            if not self.buffer:
                return
            batch = self.buffer
            self.buffer = []

        try:
            log_storage.add_alerts_batch(batch)
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{current_time}] Flushed {len(batch)} alerts to database.")
        except Exception as e:
            logger.error(f"Failed to flush alerts batch: {e}")

    def stop(self):
        self.running = False
        self.flush()

alerts_buffer = AlertsBuffer(batch_size=1000, flush_interval=10)

@app.post("/alerts")
def ingest_alert(payload: Dict[str, Any] = Body(...)):
    alerts_buffer.add_alert(payload)
    
    # If the buffer is full, we can trigger an immediate flush in the background
    # But for simplicity and to strictly follow the interval/size logic, we can also check here
    if len(alerts_buffer.buffer) >= alerts_buffer.batch_size:
        # Trigger an asynchronous flush to not block the current request
        threading.Thread(target=alerts_buffer.flush, daemon=True).start()
        
    return {"status": "ok", "message": "Alert queued for batch insertion"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

