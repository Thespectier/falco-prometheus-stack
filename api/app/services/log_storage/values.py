"""取值归一化，以及数据库行到接口结构的转换。

时间戳在库里统一存 Unix 秒：Falco 的 ISO 字符串与不同精度的时间戳都在这里折算成
同一种表示。容器标识按 容器名 → 容器 ID → Pod 名 → 主机名 的顺序回退，保证同一
容器的事件落在同一把键上。

接口返回的时间统一加东八区偏移——前端直接展示字符串，不做时区换算。
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

# 超过该值即认为不是"秒"形态的时间戳
_SECONDS_UPPER_BOUND = 1e11

# 展示用偏移：东八区
_DISPLAY_OFFSET_SECONDS = 8 * 3600


def container_id_of(fields: Dict[str, Any], fallback: Optional[str] = None) -> str:
    """按回退顺序推断容器标识，全部落空时归到 unknown。"""
    resolved = (
        fields.get("container.name")
        or fields.get("container.id")
        or fields.get("k8s.pod.name")
        or fallback
        or "unknown"
    )
    return str(resolved) if resolved else "unknown"


def epoch_seconds(value: Any) -> float:
    """把事件里的时间取值折算成 Unix 秒。

    折算口径沿用既有实现：小于 1e11 视为秒，否则除以 1e9。ISO 字符串解析失败或取值
    缺失时退回当前时间，宁可时间戳不精确也不丢事件。
    """
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except Exception:
            return datetime.utcnow().timestamp()
    if isinstance(value, (int, float)):
        return value if value < _SECONDS_UPPER_BOUND else value / 1e9
    return datetime.utcnow().timestamp()


def event_row(event: Dict[str, Any]) -> tuple:
    """一条 Falco 事件 → events 表的一行。"""
    fields = event.get("output_fields", {})
    return (
        container_id_of(fields, event.get("hostname")),
        epoch_seconds(event.get("time") or fields.get("evt.time") or fields.get("evt.time.iso8601")),
        event.get("rule", "unknown"),
        event.get("priority", "unknown"),
        event.get("source", "unknown"),
        json.dumps(fields, ensure_ascii=False),
        json.dumps(event.get("tags", [])),
        json.dumps(event),
    )


def alert_row(fields: Dict[str, Any], category: str, reason: str, attribute_value: str = "") -> tuple:
    """一条未命中画像的事件 → alerts 表的一行。

    告警优先级固定为 Warning：能进到这里的都是"画像之外"的事件，具体等级由下游
    按 category 再定。
    """
    return (
        container_id_of(fields),
        epoch_seconds(fields.get("evt.time") or fields.get("evt.time.iso8601")),
        category,
        "Warning",
        reason,
        fields.get("evt.type", ""),
        fields.get("proc.name", ""),
        fields.get("fd.name", ""),
        json.dumps(fields, ensure_ascii=False),
        attribute_value,
    )


def log_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    """events 行 → 接口返回的日志条目。"""
    return {
        "timestamp": datetime.fromtimestamp(row["timestamp"] + _DISPLAY_OFFSET_SECONDS).isoformat(),
        "rule": row["rule"],
        "priority": row["priority"],
        "source": row["source"],
        "output": json.dumps(row["output"]) if isinstance(row["output"], dict) else row["output"],
        "tags": row["tags"]
        if isinstance(row["tags"], list)
        else (json.loads(row["tags"]) if row["tags"] else []),
    }


def alert_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    """alerts 行 → 接口返回的告警条目。"""
    return {
        "container_id": row["container_id"],
        "timestamp": datetime.fromtimestamp(row["timestamp"] + _DISPLAY_OFFSET_SECONDS).isoformat(),
        "category": row["category"],
        "reason": row["reason"],
        "evt_type": row["evt_type"],
        "proc_name": row["proc_name"],
        "fd_name": row["fd_name"],
        "output": json.dumps(row["output"]) if isinstance(row["output"], dict) else row["output"],
        "attribute_value": row["attribute_value"],
    }


def incident_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    """incidents 行 → 接口返回的事件条目。"""
    return {
        "id": row["id"],
        "container_id": row["container_id"],
        "timestamp": datetime.fromtimestamp(row["timestamp"] + _DISPLAY_OFFSET_SECONDS).isoformat(),
        "threat_score": row["threat_score"],
        "cluster_id": row["cluster_id"],
        "attribute_name": row["attribute_name"],
        "attribute_value": row["attribute_value"],
        "event_type": row["event_type"],
        "process_name": row["process_name"],
        "alert_content": row["alert_content"],
        "details": row["details"],
        "analysis_window": row["analysis_window"],
        "similarity_threshold": row["similarity_threshold"],
        "created_at": datetime.fromtimestamp(row["created_at"] + _DISPLAY_OFFSET_SECONDS).isoformat(),
        "analysis": row["analysis"],
    }
