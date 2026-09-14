"""Hanabi 主工作进程：消费 Falco 日志 → 维护各容器的 HBT 模型 → 定期落盘。

一个工作进程同时维护多个容器的模型（每个容器一棵行为树），按固定间隔把模型快照写成
JSON 供后端读取。落盘用"先写临时文件再改名"的方式，避免后端读到写了一半的文件。
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict

# 以脚本方式运行时（python hanabi/worker.py）需要能 import hanabi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hanabi.models.event_parser import EventParser
from hanabi.models.hbt import HBTModel
from hanabi.utils.queue import DockerLogQueue

# Configuration
HBT_STORAGE_PATH = os.getenv("HBT_STORAGE_PATH", "/app/data/hbt")
FALCO_CONTAINER = os.getenv("FALCO_CONTAINER", "43039infrasecurity-falco")
SAVE_INTERVAL_SECONDS = 30

# 启动后先等一段时间：容器编排刚起来时 Falco 还在初始化，过早开始消费会漏事件
STARTUP_DELAY_SECONDS = 30

# 取队列的等待上限，留出检查落盘间隔的机会
_QUEUE_READ_TIMEOUT_SECONDS = 1

# 分类标签 → 模型上的方法名
_CATEGORY_HANDLERS = {
    "process": "add_process_event",
    "network": "add_network_event",
    "file": "add_file_event",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HanabiWorker")


class HanabiWorker:
    """按容器维护 HBT 模型，并定期把快照写到共享存储。"""

    def __init__(self, container_name: str, storage_path: str):
        self.container_name = container_name
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.log_queue = DockerLogQueue(container_name=container_name)
        self.event_parser = EventParser()

        # container_id -> HBTModel
        self.models: Dict[str, HBTModel] = {}

        self.running = False
        self.last_save_time = time.time()

    def get_or_create_model(self, container_id: str) -> HBTModel:
        """取容器对应的模型，没有就建一个。"""
        if container_id not in self.models:
            logger.info(f"Creating new HBT model for container: {container_id}")
            self.models[container_id] = HBTModel(container_id)
        return self.models[container_id]

    def save_snapshots(self):
        """把所有模型快照写到存储目录。"""
        logger.info(f"Saving snapshots for {len(self.models)} containers...")
        for cid, model in self.models.items():
            try:
                self._write_snapshot(cid, model.get_model())
            except Exception as e:
                logger.error(f"Failed to save snapshot for {cid}: {e}")
        self.last_save_time = time.time()

    def _write_snapshot(self, container_id: str, data: dict):
        """先写临时文件再改名，保证后端不会读到半截 JSON。"""
        file_path = self.storage_path / f"{container_id}.json"
        temp_path = file_path.with_suffix('.tmp')
        with open(temp_path, 'w') as handle:
            json.dump(data, handle, ensure_ascii=False, default=str)
        temp_path.replace(file_path)

    def start(self):
        """主循环：等 Falco 就绪 → 消费事件 → 按间隔落盘。"""
        self.running = True
        logger.info("Startup delay 30s before processing")
        time.sleep(STARTUP_DELAY_SECONDS)
        self.log_queue.start()

        logger.info(f"Hanabi Worker started. Monitoring {self.container_name}")

        processed = 0
        try:
            while self.running:
                json_obj = self.log_queue.get(timeout=_QUEUE_READ_TIMEOUT_SECONDS)

                if json_obj:
                    processed += 1
                    print("log:", processed)
                    self.process_event(json_obj)

                if time.time() - self.last_save_time > SAVE_INTERVAL_SECONDS:
                    self.save_snapshots()

        except KeyboardInterrupt:
            logger.info("Stopping worker...")
        finally:
            self.stop()

    def process_event(self, event: dict):
        """把一条事件并入对应容器的模型。"""
        try:
            output_fields = self.event_parser.extract_output_fields(event)
            container_id = output_fields.get("container.name") or "unknown"

            # 宿主机事件拿不到容器名，直接跳过
            if not container_id or container_id == "unknown":
                return

            model = self.get_or_create_model(container_id)
            handler = _CATEGORY_HANDLERS.get(self.event_parser.categorize_event(event))
            if handler is not None:
                getattr(model, handler)(output_fields)

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    def stop(self):
        """停止消费、落盘并退出。"""
        self.running = False
        self.log_queue.stop()
        self.save_snapshots()
        logger.info("Worker stopped.")


def signal_handler(sig, frame):
    """收到 SIGINT / SIGTERM 时走正常退出路径（触发 stop 落盘）。"""
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    worker = HanabiWorker(
        container_name=FALCO_CONTAINER,
        storage_path=HBT_STORAGE_PATH
    )
    worker.start()
