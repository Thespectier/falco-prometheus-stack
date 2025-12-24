import os
import time
import json
import logging
from typing import List, Dict, Any

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ReducerService")


def _list_containers(client: httpx.Client) -> List[str]:
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


def _alerts_to_dataframe(alerts: List[Dict[str, Any]]) -> pd.DataFrame:
    # Build behavior frequency counts by (proc_name, evt_type)
    behavior_counts: Dict[tuple[str, str], int] = {}
    for a in alerts:
        evt_type = str(a.get("evt_type") or "")
        proc_name = str(a.get("proc_name") or "")
        key = (proc_name, evt_type)
        behavior_counts[key] = behavior_counts.get(key, 0) + 1

    rows: List[Dict[str, Any]] = []
    for i, a in enumerate(alerts):
        # Map alert fields to reducer schema
        ts = a.get("timestamp") or a.get("timestamp_iso") or ""
        category = a.get("category") or ""
        reason = a.get("reason") or category or ""
        evt_type = str(a.get("evt_type") or "")
        proc_name = str(a.get("proc_name") or "")
        fd_name = str(a.get("fd_name") or "")
        output = a.get("output") or ""
        attribute_value = str(a.get("attribute_value") or "")

        # frequency by (proc_name, evt_type)
        behavior = (proc_name, evt_type)
        freq = behavior_counts.get(behavior, 1)

        if not attribute_value:
             attribute_value = proc_name or fd_name or evt_type or ""
        
        rows.append({
            "异常事件序号": i,
            "异常属性名": reason,
            "异常属性值": attribute_value,
            "异常频次": freq,
            "进程名": proc_name,
            "事件类型": evt_type,
            "事件详情": output,
            "完整日志": output,
            "日志时间": ts,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.fillna("")
        df["异常频次"] = pd.to_numeric(df["异常频次"], errors="coerce").fillna(0)
        df["异常事件序号"] = pd.to_numeric(df["异常事件序号"], errors="coerce").fillna(0)
        # Sync with hanabi logic: include process name and boost weight
        # Weight adjustment: 
        # - Attribute Name/Value: x5
        # - Process/Event Type: x10
        df["告警内容"] = df.apply(
            lambda x: f"{x['异常属性名']} " + 
                      f"{x['异常属性值']} " + 
                      f"{x['进程名']} " + 
                      f"{x['事件类型']} " ,
            axis=1
        )
        df["威胁特征"] = df.apply(lambda x: f"进程:{x['进程名']} 事件:{x['事件类型']} 详情:{x['事件详情']} 频次:{x['异常频次']}", axis=1)
    return df


def _reduce_for_container(container_id: str, alerts: List[Dict[str, Any]]):
    from hanabi.reducer import AlertReducer  # local import to avoid heavy deps on startup

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

    incidents: List[Dict[str, Any]] = []
    for _, row in reduced.iterrows():
        incidents.append({
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
        })
    return incidents


def run_once():
    logger.info("Reducer cycle started")
    with httpx.Client(base_url=PROMETHEUS_URL, timeout=5.0) as client:
        names = _list_containers(client)
    logger.info(f"Containers discovered: {names}")

    total_incidents = 0
    for name in names:
        if name == "unknown":
            continue
        alerts = log_storage.get_alerts(container_id=name, window_seconds=WINDOW_SECONDS, limit=2000, offset=0)
        incidents = _reduce_for_container(name, alerts)
        for inc in incidents:
            log_storage.add_incident(
                container_id=inc["container_id"],
                timestamp=inc["timestamp"],
                threat_score=inc["threat_score"],
                cluster_id=inc["cluster_id"],
                attribute_name=inc["attribute_name"],
                attribute_value=inc["attribute_value"],
                event_type=inc["event_type"],
                process_name=inc["process_name"],
                alert_content=inc["alert_content"],
                details=inc["details"],
                analysis_window=inc["analysis_window"],
                similarity_threshold=inc["similarity_threshold"],
            )
        logger.info(f"Container {name}: alerts={len(alerts)} incidents={len(incidents)}")
        total_incidents += len(incidents)

    logger.info(f"Reducer cycle completed. Total incidents: {total_incidents}")


def main():
    interval = POLL_INTERVAL_SECONDS
    logger.info(f"Reducer service starting. Interval={interval}s, window={WINDOW_SECONDS}s")
    time.sleep(180)
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"Reducer cycle failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
