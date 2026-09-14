"""日志摄取与实时推送。

采集侧通过内部接口把日志成批推进来，后端再通过 WebSocket 广播给订阅了该容器的
前端。空批次直接返回，不触发广播。
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body, WebSocket, WebSocketDisconnect

from api.app.services.websocket_manager import websocket_manager

router = APIRouter()
logger = logging.getLogger("LogsRouter")


@router.websocket("/ws/{container_id}")
async def websocket_endpoint(websocket: WebSocket, container_id: str):
    """前端订阅某容器日志的 WebSocket 端点。"""
    await websocket_manager.connect(websocket, container_id)
    try:
        while True:
            # 目前只用于保活；后续的暂停、过滤等前端指令也走这条通道
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, container_id)


@router.post("/internal/ingest")
async def ingest_logs(logs: List[Dict[str, Any]] = Body(...)):
    """采集侧推送日志的内部接口。"""
    if not logs:
        return {"status": "ok", "count": 0}

    await websocket_manager.broadcast_batch(logs)

    return {"status": "ok", "count": len(logs)}
