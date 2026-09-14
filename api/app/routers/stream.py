"""事件流的 SSE 端点。

当前只发心跳：真正的告警推送由 WebSocket 通道承担，这里保留接口是为了兼容已经
接入的前端代码，避免它们改调用方式。
"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

_HEARTBEAT_INTERVAL_SECONDS = 30
_SSE_MEDIA_TYPE = "text/event-stream"


async def event_generator(container_id: str):
    """按固定间隔产生心跳帧。"""
    while True:
        yield f"data: {{'type': 'heartbeat', 'container': '{container_id}'}}\n\n"
        await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)


@router.get("/{id}")
async def stream_events(id: str):
    """某容器的事件 SSE 流。"""
    return StreamingResponse(event_generator(id), media_type=_SSE_MEDIA_TYPE)
