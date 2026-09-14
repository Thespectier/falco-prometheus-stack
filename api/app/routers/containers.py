"""容器维度的查询接口。

容器列表没有独立存储，直接由 Prometheus 现算：最近事件时间戳给出"有哪些
容器"，事件速率给出各自的活跃度。
"""

from typing import Optional

from fastapi import APIRouter

from api.app.services.log_storage import log_storage
from api.app.services.prometheus import prometheus_service

router = APIRouter()

# 最近一次事件时间戳，用于枚举活跃过的容器
_LAST_SEEN_QUERY = "syscall_last_event_timestamp_seconds"

# 各容器 5 分钟事件速率
_RATE_QUERY = "sum by (container_name) (rate(syscall_events_total[5m]))"


@router.get("")
async def list_containers():
    """列出被监控容器及其当前活跃度。"""
    last_seen = await prometheus_service.query(_LAST_SEEN_QUERY)
    rates = await prometheus_service.query(_RATE_QUERY)

    containers: dict = {}

    if last_seen.get("status") == "success":
        for sample in last_seen.get("data", {}).get("result", []):
            name = sample["metric"].get("container_name")
            if not name:
                continue
            containers[name] = {
                "id": name,  # 目前容器名即标识，接入运行时后再换成容器 ID
                "name": name,
                "last_seen": float(sample["value"][1]),
                "event_rate": 0.0,
            }

    if rates.get("status") == "success":
        for sample in rates.get("data", {}).get("result", []):
            name = sample["metric"].get("container_name")
            known = containers.get(name) if name else None
            if known is not None:
                known["event_rate"] = float(sample["value"][1])

    return list(containers.values())


@router.get("/{id}/logs")
async def get_container_logs(
    id: str,
    start: Optional[int] = None,
    end: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
):
    """按容器取历史日志（分页）。

    start/end 在存储层尚无对应的过滤实现，保留参数是为了不破坏已发布的前端调用。
    """
    logs = log_storage.get_logs(container_id=id, limit=limit, offset=offset)

    return {
        "container_id": id,
        "logs": logs,
    }
