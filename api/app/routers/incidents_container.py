from fastapi import APIRouter
from api.app.services.log_storage import log_storage

router = APIRouter()

@router.get("")
async def get_container_incidents(
    id: str,
    window_seconds: int = 0,
    limit: int = 500,
    offset: int = 0,
):
    items = log_storage.get_incidents(container_id=id, window_seconds=window_seconds, limit=limit, offset=offset)
    return {
        "container_id": id,
        "incidents": items,
    }

