"""WebSocket 广播：把摄取端推来的日志分发给订阅了对应容器的前端。

连接按容器分组存放，另有一个 "all" 分组供总览页面使用。某个分组空了就立刻删除，
避免长时间运行后堆积大量空列表。

报文按前端 LogEvent 结构拼装：output / tags 以字符串下发，前端只做展示、不再解析。
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Tuple

from fastapi import WebSocket

logger = logging.getLogger("WebSocketManager")

# 认不出容器的日志既不进画像也不推送
_UNKNOWN_CONTAINER = "unknown"

# 总览页面订阅的分组名
_GLOBAL_GROUP = "all"

# 小于该值的时间戳按秒解释，否则按纳秒
_SECONDS_UPPER_BOUND = 1e11


def _message_timestamp(value) -> float:
    """把日志里的时间折算成秒。

    无法识别的取值退回当前时间：前端按时间排序展示，宁可时间不精确也不能丢消息。
    """
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()
    if isinstance(value, (int, float)):
        return value if value < _SECONDS_UPPER_BOUND else value / 1e9
    return time.time()


def _frontend_message(log: Dict) -> Tuple[str, str]:
    """整理一条日志，返回 (容器标识, 报文本)。

    容器未知时返回 ("", "")，调用方据此跳过，不再做时间与字段处理。
    """
    fields = log.get("output_fields", {})
    container_id = fields.get("container.name") or _UNKNOWN_CONTAINER
    if container_id == _UNKNOWN_CONTAINER:
        return "", ""

    timestamp = _message_timestamp(
        log.get("time") or fields.get("evt.time") or fields.get("evt.time.iso8601")
    )
    message = json.dumps(
        {
            "timestamp": timestamp,
            "rule": log.get("rule", "unknown"),
            "priority": log.get("priority", "unknown"),
            "source": log.get("source", "unknown"),
            "output": json.dumps(fields, ensure_ascii=False),
            "tags": json.dumps(log.get("tags", [])),
            "container_id": container_id,
        }
    )
    return container_id, message


class WebSocketManager:
    """维护各容器的活跃连接，并向订阅者广播日志。"""

    def __init__(self):
        # 容器标识 -> 该容器的连接列表；"all" 键表示订阅全部
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, container_id: str = _GLOBAL_GROUP):
        """接受连接并登记到对应分组。"""
        await websocket.accept()
        self.active_connections.setdefault(container_id, []).append(websocket)
        logger.info(
            f"WebSocket connected for container: {container_id}. "
            f"Active clients: {len(self.active_connections[container_id])}"
        )

    def disconnect(self, websocket: WebSocket, container_id: str = _GLOBAL_GROUP):
        """注销连接；分组空了就删掉这个键。"""
        subscribers = self.active_connections.get(container_id)
        if subscribers is not None and websocket in subscribers:
            subscribers.remove(websocket)
            if not subscribers:
                del self.active_connections[container_id]
        logger.info(f"WebSocket disconnected for container: {container_id}")

    async def broadcast_batch(self, logs: List[Dict]):
        """把一批日志发给对应的容器订阅者与总览订阅者。"""
        for log in logs:
            container_id, message = _frontend_message(log)
            if not message:
                continue

            for group in (container_id, _GLOBAL_GROUP):
                subscribers = self.active_connections.get(group)
                if subscribers:
                    await self._send_to_group(subscribers, message)

    async def _send_to_group(self, connections: List[WebSocket], message: str):
        """向一组连接发送；发送失败的连接在本轮结束后剔除。"""
        failed = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                failed.append(connection)

        for connection in failed:
            try:
                connections.remove(connection)
            except ValueError:
                pass


websocket_manager = WebSocketManager()
