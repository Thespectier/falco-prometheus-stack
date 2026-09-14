"""按容器查询告警。"""

from fastapi import APIRouter

from api.app.services.log_storage import log_storage

router = APIRouter()


@router.get("")
async def get_container_alerts(
    id: str,
    window_seconds: int = 0,
    limit: int = 500,
    offset: int = 0
):
    """取某个容器在时间窗内的告警；window_seconds=0 表示不限窗口。"""
    alerts = log_storage.get_alerts(container_id=id, window_seconds=window_seconds, limit=limit, offset=offset)
    return {
        "container_id": id,
        "alerts": alerts
    }
