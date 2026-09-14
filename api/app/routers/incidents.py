"""事件（incident）列表。"""

from typing import Optional

from fastapi import APIRouter, Query

from api.app.services.log_storage import log_storage

router = APIRouter()


@router.get("")
async def list_incidents(
    container_id: Optional[str] = Query(default=None),
    window_seconds: int = 0,
    limit: int = 500,
    offset: int = 0,
):
    """按容器（可选）与时间窗列出事件。"""
    return log_storage.get_incidents(
        container_id=container_id,
        window_seconds=window_seconds,
        limit=limit,
        offset=offset,
    )
