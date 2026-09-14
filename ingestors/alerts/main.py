"""告警摄取服务：接收 hanabi 侧投递的未命中告警并批量入库。

告警是突发式的：画像从学习期切到检测期时会连着报出一批，逐条插入会打满数据库连接。
因此先进内存缓冲，按批大小或时间窗刷写。
"""

import atexit
import logging
import threading
import time
from typing import Any, Dict, List

from fastapi import Body, FastAPI

from api.app.services.log_storage import log_storage

logger = logging.getLogger("AlertsIngestor")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Alerts Ingestor", version="0.1.0")

_DEFAULT_BATCH_SIZE = 1000
_DEFAULT_FLUSH_INTERVAL_SECONDS = 10


class AlertsBuffer:
    """线程安全的告警缓冲：满批或超时后写入数据库。"""

    def __init__(
        self,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        flush_interval: int = _DEFAULT_FLUSH_INTERVAL_SECONDS,
    ):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.running = True
        self.worker_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.worker_thread.start()
        atexit.register(self.stop)

    def add_alert(self, payload: Dict[str, Any]):
        """入缓冲，调用方不关心刷写时机。"""
        with self.lock:
            self.buffer.append(payload)

    def _flush_loop(self):
        """后台线程：按固定间隔刷写。"""
        while self.running:
            time.sleep(self.flush_interval)
            self.flush()

    def flush(self):
        """把当前缓冲整体交给存储层。

        取出缓冲后立刻释放锁：写库是耗时操作，不能占着锁阻塞请求线程。
        写入失败只记日志，这批数据不再重试（下一批继续）。
        """
        with self.lock:
            if not self.buffer:
                return
            batch = self.buffer
            self.buffer = []

        try:
            log_storage.add_alerts_batch(batch)
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{current_time}] Flushed {len(batch)} alerts to database.")
        except Exception as error:
            logger.error(f"Failed to flush alerts batch: {error}")

    def stop(self):
        """停止后台线程，并把剩余告警刷出去。"""
        self.running = False
        self.flush()


alerts_buffer = AlertsBuffer(batch_size=_DEFAULT_BATCH_SIZE, flush_interval=_DEFAULT_FLUSH_INTERVAL_SECONDS)


@app.post("/alerts")
def ingest_alert(payload: Dict[str, Any] = Body(...)):
    """接收一条告警。

    缓冲满时另起线程立即刷写，不阻塞当前请求；未满则等后台线程的时间窗。
    """
    alerts_buffer.add_alert(payload)

    if len(alerts_buffer.buffer) >= alerts_buffer.batch_size:
        threading.Thread(target=alerts_buffer.flush, daemon=True).start()

    return {"status": "ok", "message": "Alert queued for batch insertion"}


@app.get("/healthz")
def healthz():
    """探针接口。"""
    return {"status": "ok"}
