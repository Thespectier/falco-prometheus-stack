"""总览页指标。

四条 PromQL 各自独立查询：某一条失败只让对应条目为空，不影响其它条目，前端
拿到的是部分结果。漏斗统计（日志 → 告警 → 事件）来自本地存储，窗口取 30 分钟，
与日志保留期保持一致。
"""

from fastapi import APIRouter

from api.app.services.log_storage import log_storage
from api.app.services.prometheus import prometheus_service

router = APIRouter()

# 漏斗统计窗口：1800 秒 = 30 分钟
_FUNNEL_WINDOW_SECONDS = 1800

# 键名就是响应字段名，改动会破坏前端契约
_OVERVIEW_QUERIES = {
    "total_rate": "sum(rate(syscall_events_total[5m]))",
    "by_priority": "sum by(priority) (rate(syscall_events_total[5m]))",
    "by_category": "sum by(rule_category) (rate(syscall_events_total[5m]))",
    "active_containers": "count(sum by(container_name) (rate(syscall_events_total[5m]) > 0))",
}


@router.get("")
async def get_overview():
    """总览：事件总速率、优先级与类别分布、活跃容器数、漏斗统计。"""
    samples = {}
    for key, query in _OVERVIEW_QUERIES.items():
        response = await prometheus_service.query(query)
        if response.get("status") == "success":
            samples[key] = response.get("data", {}).get("result", [])
        else:
            samples[key] = []

    overview = {
        "total_events_rate": 0.0,
        "priority_distribution": [],
        "category_distribution": [],
        "active_containers_count": 0,
        "funnel_stats": log_storage.get_funnel_stats(window_seconds=_FUNNEL_WINDOW_SECONDS),
    }

    if samples["total_rate"]:
        try:
            overview["total_events_rate"] = float(samples["total_rate"][0]["value"][1])
        except (IndexError, ValueError):
            # 采样值缺失或非数值时保留 0，不把 Prometheus 的脏数据透给前端
            pass

    for sample in samples["by_priority"]:
        try:
            overview["priority_distribution"].append(
                {
                    "priority": sample["metric"].get("priority", "unknown"),
                    "value": float(sample["value"][1]),
                }
            )
        except (ValueError, KeyError):
            pass

    for sample in samples["by_category"]:
        try:
            overview["category_distribution"].append(
                {
                    "category": sample["metric"].get("rule_category", "unknown"),
                    "value": float(sample["value"][1]),
                }
            )
        except (ValueError, KeyError):
            pass

    if samples["active_containers"]:
        try:
            overview["active_containers_count"] = int(samples["active_containers"][0]["value"][1])
        except (IndexError, ValueError):
            pass

    return overview
