"""日志摄取服务：从 Falco 容器拉日志，按批推给后端 API。

这里不直接写库：后端负责入库并通过 WebSocket 分发给前端。搬运用批大小与刷写间隔
共同决定延迟，默认 3 秒，前端基本感觉不到滞后。
"""

import logging
import os
import time
from typing import List

import httpx

from hanabi.utils.queue import DockerLogQueue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LogsIngestor")

FALCO_CONTAINER = os.getenv("FALCO_CONTAINER", "43039infrasecurity-falco")
API_URL = os.getenv(
    "API_URL",
    "http://43039infrasecurity-api:8000/infrasecurity/api/logs/internal/ingest",
)

# 批大小与刷写间隔：谁先到就刷
BATCH_SIZE = 5000
FLUSH_INTERVAL = 3.0

# 单次取队列的等待上限，留出时间检查时间窗
_QUEUE_READ_TIMEOUT_SECONDS = 0.1

_MAX_QUEUE_SIZE = 100000
_PUSH_TIMEOUT_SECONDS = 5.0


def flush_buffer(client: httpx.Client, buffer: List[dict]):
    """把缓冲推给后端。

    失败只记日志：调用方随后仍会清空缓冲，因此这一批会丢；日志本身的缺口由上游
    Falco 的落盘日志兜底。
    """
    if not buffer:
        return
    try:
        resp = client.post(API_URL, json=buffer)
        if resp.status_code != 200:
            logger.error(f"Failed to push logs to API: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to push logs to API: {e}")


def _drain_queue(log_queue: DockerLogQueue, buffer: List[dict]) -> None:
    """把队列里已到达的一条日志搬进缓冲，不阻塞主循环。"""
    try:
        obj = log_queue.get(timeout=_QUEUE_READ_TIMEOUT_SECONDS)
        if obj:
            buffer.append(obj)
    except Exception:
        # 队列空或读取失败都按"这一轮没有数据"处理
        pass


def run():
    """主循环：搬运 + 按条件刷写。"""
    log_queue = DockerLogQueue(container_name=FALCO_CONTAINER, max_queue_size=_MAX_QUEUE_SIZE)
    log_queue.start()

    buffer: List[dict] = []
    last_flush_time = time.time()

    logger.info(f"LogsIngestor started. Streaming to {API_URL}")

    with httpx.Client(timeout=_PUSH_TIMEOUT_SECONDS) as client:
        try:
            while True:
                _drain_queue(log_queue, buffer)

                now = time.time()
                batch_full = len(buffer) >= BATCH_SIZE
                window_elapsed = len(buffer) > 0 and now - last_flush_time >= FLUSH_INTERVAL
                if batch_full or window_elapsed:
                    flush_buffer(client, buffer)
                    buffer.clear()
                    last_flush_time = now

        except KeyboardInterrupt:
            logger.info("Stopping LogsIngestor...")
            # 退出前把缓冲里剩下的推出去，避免丢最后一批
            flush_buffer(client, buffer)
        finally:
            log_queue.stop()


if __name__ == "__main__":
    run()
