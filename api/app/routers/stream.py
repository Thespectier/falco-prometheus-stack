from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

async def event_generator(container_id: str):
    while True:
        # Placeholder for event generation logic
        yield f"data: {{'type': 'heartbeat', 'container': '{container_id}'}}\n\n"
        await asyncio.sleep(30)

@router.get("/{id}")
async def stream_events(id: str):
    """SSE stream for events and alerts"""
    return StreamingResponse(event_generator(id), media_type="text/event-stream")
