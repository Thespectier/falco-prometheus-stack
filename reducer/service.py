"""归约服务：把告警按容器聚类消减成"事件（incident）"。

主循环每轮做两件事：

1. 到点清理过期的告警（事件清理与 VACUUM 目前暂停，见 `main`）
2. 从 Prometheus 发现活跃容器 → 取窗口内的告警 → 消减 → 落库

pandas 与 hanabi.reducer 在模块顶层导入，但真正的消减器在 `_reduce_for_container`
里才加载：归约服务单独跑得起来，不必等重型依赖就绪。
"""

import logging
import os
import time
from typing import Any, Dict, List

import httpx
import pandas as pd

# Reuse project services
from api.app.services.log_storage import log_storage

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
POLL_INTERVAL_SECONDS = int(os.getenv("REDUCER_INTERVAL_SECONDS", "270"))
WINDOW_SECONDS = int(os.getenv("REDUCER_WINDOW_SECONDS", "300"))
SIMILARITY_THRESHOLD = float(os.getenv("REDUCER_SIMILARITY", "0.6"))
THREAT_THRESHOLD = float(os.getenv("REDUCER_THREAT_THRESHOLD", "60.0"))
MAX_PER_CLUSTER = int(os.getenv("REDUCER_MAX_PER_CLUSTER", "1"))

# 事件保留期，默认 0.5 小时
RETENTION_DAYS = float(os.getenv("RETENTION_DAYS", str(0.5 / 24)))
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "3600"))  # 1 hour
VACUUM_INTERVAL = int(os.getenv("VACUUM_INTERVAL", "86400"))  # 24 hours

# 告警保留期，默认 3 小时
ALERTS_RETENTION_DAYS = float(os.getenv("ALERTS_RETENTION_DAYS", str(3.0 / 24)))

# 单次从 Prometheus 发现的容器最多取多少条告警
_ALERTS_PER_CONTAINER = 2000

# 主循环启动前的等待：让数据库与 Prometheus 先就绪
_STARTUP_DELAY_SECONDS = 60


def _derive_alerts_cleanup_interval(retention_days: float) -> int:
    """清理间隔取保留期的一半，并夹在 5 分钟到 24 小时之间。

    清理要比保留期更频繁，否则库里会长期堆着已经过期的数据；上下限则防止保留期被
    配成极端值（比如 1 分钟或 30 天）时清理过于频繁或形同虚设。
    """
    retention_seconds = retention_days * 86400
    return max(300, min(86400, int(retention_seconds / 2)))


ALERTS_CLEANUP_INTERVAL = int(os.getenv("ALERTS_CLEANUP_INTERVAL", str(_derive_alerts_cleanup_interval(ALERTS_RETENTION_DAYS))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ReducerService")


def _list_containers(client: httpx.Client) -> List[str]:
    """查出最近上报过事件的容器名，去重后排序。

    容器名来自 exporter 写入的 `syscall_last_event_timestamp_seconds` 标签；
    查询失败时返回空列表，让这一轮空跑而不是让整个循环中断。
    """
    names: List[str] = []
    try:
        resp = client.get("/api/v1/query", params={"query": "syscall_last_event_timestamp_seconds"})
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", {}).get("result", []):
            name = item.get("metric", {}).get("container_name")
            if name:
                names.append(name)
    except Exception as e:
        logger.error(f"Failed to query containers from Prometheus: {e}")
    return sorted(set(names))


def _behavior_counts(alerts: List[Dict[str, Any]]) -> Dict[tuple, int]:
    """统计 (进程名, 事件类型) 组合的出现次数，作为该行为的"异常频次"。"""
    counts: Dict[tuple, int] = {}
    for item in alerts:
        evt_type = str(item.get("evt_type") or "")
        proc_name = str(item.get("proc_name") or "")
        key = (proc_name, evt_type)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _alert_to_row(item: Dict[str, Any], index: int, counts: Dict[tuple, int]) -> Dict[str, Any]:
    """把一条告警映射成 reducer 需要的列。"""
    ts = item.get("timestamp") or item.get("timestamp_iso") or ""
    category = item.get("category") or ""
    reason = item.get("reason") or category or ""
    evt_type = str(item.get("evt_type") or "")
    proc_name = str(item.get("proc_name") or "")
    fd_name = str(item.get("fd_name") or "")
    output = item.get("output") or ""
    attribute_value = str(item.get("attribute_value") or "")

    if not attribute_value:
        # 属性值缺失时按 进程名 → 文件名 → 事件类型 回退，保证相似度有可用文本
        attribute_value = proc_name or fd_name or evt_type or ""

    return {
        "异常事件序号": index,
        "异常属性名": reason,
        "异常属性值": attribute_value,
        "异常频次": counts.get((proc_name, evt_type), 1),
        "进程名": proc_name,
        "事件类型": evt_type,
        "事件详情": output,
        "完整日志": output,
        "日志时间": ts,
    }


def _alerts_to_dataframe(alerts: List[Dict[str, Any]]) -> pd.DataFrame:
    """把告警列表转成 reducer 需要的 DataFrame。

    这里的"告警内容"不带权重，与 CSV 载入路径（`hanabi.reducer` 的预处理会给属性名/值
    各 ×5、进程名 ×10）不同：线上路径只走这里。两处口径如需统一，要单独评估对既有
    聚类结果的影响。
    """
    counts = _behavior_counts(alerts)
    df = pd.DataFrame([_alert_to_row(item, index, counts) for index, item in enumerate(alerts)])
    if df.empty:
        return df

    df = df.fillna("")
    df["异常频次"] = pd.to_numeric(df["异常频次"], errors="coerce").fillna(0)
    df["异常事件序号"] = pd.to_numeric(df["异常事件序号"], errors="coerce").fillna(0)

    df["告警内容"] = df.apply(
        lambda x: f"{x['异常属性名']} " +
                  f"{x['异常属性值']} " +
                  f"{x['进程名']} " +
                  f"{x['事件类型']} ",
        axis=1
    )
    df["威胁特征"] = df.apply(
        lambda x: f"进程:{x['进程名']} 事件:{x['事件类型']} 详情:{x['事件详情']} 频次:{x['异常频次']}",
        axis=1
    )
    return df


def _incident_from_row(container_id: str, row) -> Dict[str, Any]:
    """消减结果的一行 → 待落库的事件字典。"""
    return {
        "container_id": container_id,
        "timestamp": time.time(),
        "threat_score": float(row.get("threat_score", 0.0)),
        "cluster_id": int(row.get("cluster", -1)) if "cluster" in row else None,
        "attribute_name": str(row.get("异常属性名", "")),
        "attribute_value": str(row.get("异常属性值", "")),
        "event_type": str(row.get("事件类型", "")),
        "process_name": str(row.get("进程名", "")),
        "alert_content": str(row.get("告警内容", "")) if "告警内容" in row else "",
        "details": str(row.get("事件详情", "")),
        "analysis_window": WINDOW_SECONDS,
        "similarity_threshold": SIMILARITY_THRESHOLD,
    }


def _reduce_for_container(container_id: str, alerts: List[Dict[str, Any]]):
    """对单个容器的告警做一次消减，返回待落库的事件列表。"""
    from hanabi.reducer import AlertReducer  # 局部导入，避免启动就拉起重型依赖

    if not alerts:
        return []

    df = _alerts_to_dataframe(alerts)

    reducer = AlertReducer()
    reduced = reducer.reduce_alerts(
        df,
        cluster_reduction=True,
        threat_threshold=THREAT_THRESHOLD,
        max_alerts_per_cluster=MAX_PER_CLUSTER,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )

    return [_incident_from_row(container_id, row) for _, row in reduced.iterrows()]


def _discover_containers() -> List[str]:
    """查一次 Prometheus 拿容器名单。"""
    with httpx.Client(base_url=PROMETHEUS_URL, timeout=5.0) as client:
        return _list_containers(client)


def run_once():
    """跑一轮：发现容器 → 逐容器取告警 → 消减 → 落库。"""
    logger.info("Reducer cycle started")
    names = _discover_containers()
    logger.info(f"Containers discovered: {names}")

    total_incidents = 0
    for name in names:
        # "unknown" 是没法归到具体容器的告警，不参与消减
        if name == "unknown":
            continue

        alerts = log_storage.get_alerts(container_id=name, window_seconds=WINDOW_SECONDS, limit=_ALERTS_PER_CONTAINER, offset=0)
        incidents = _reduce_for_container(name, alerts)

        for incident in incidents:
            log_storage.add_incident(**incident)

        logger.info(f"Container {name}: alerts={len(alerts)} incidents={len(incidents)}")
        total_incidents += len(incidents)

    logger.info(f"Reducer cycle completed. Total incidents: {total_incidents}")


def _cleanup_alerts_if_due(last_cleanup_ts: float, now: float) -> float:
    """到点就清理过期告警，返回新的"上次清理时间"。"""
    if now - last_cleanup_ts <= ALERTS_CLEANUP_INTERVAL:
        return last_cleanup_ts

    logger.info(f"Running alerts cleanup (retention={ALERTS_RETENTION_DAYS:.4f} days)...")
    log_storage.cleanup_old_alerts(retention_days=ALERTS_RETENTION_DAYS)
    return now


def main():
    """主循环：告警清理 → 消减 → 休眠。"""
    interval = POLL_INTERVAL_SECONDS
    logger.info(f"Reducer service starting. Interval={interval}s, window={WINDOW_SECONDS}s")

    # 先等一会，让数据库与 Prometheus 就绪
    time.sleep(_STARTUP_DELAY_SECONDS)

    last_alerts_cleanup_ts = 0

    while True:
        try:
            now = time.time()

            # 事件清理（DELETE）与数据 VACUUM 目前暂停：原实现按 CLEANUP_INTERVAL /
            # VACUUM_INTERVAL 调 log_storage.cleanup_old_data / vacuum_logs_db，
            # 恢复时在这里各补一个"上次执行时间戳"即可。现在只保留告警清理（见下）。

            # 告警清理（DELETE）
            last_alerts_cleanup_ts = _cleanup_alerts_if_due(last_alerts_cleanup_ts, now)

            # 消减
            run_once()
        except Exception as e:
            logger.error(f"Reducer cycle failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
