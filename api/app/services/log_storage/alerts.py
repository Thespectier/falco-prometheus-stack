"""alerts 表：画像未命中告警的写入、查询与按类别统计。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2.extras import execute_batch

from .base import LOG_STORAGE_DEBUG, logger
from .values import alert_entry, alert_row

_INSERT_SQL = """
    INSERT INTO alerts (container_id, timestamp, category, priority, reason, evt_type, proc_name, fd_name, output, attribute_value)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_SELECT_COLUMNS = (
    "SELECT container_id, timestamp, category, reason, evt_type, proc_name, fd_name, output, attribute_value"
    " FROM alerts"
)

_STATS_COLUMNS = "SELECT category, priority, COUNT(*) as cnt FROM alerts"
_STATS_GROUPING = "GROUP BY category, priority"

# container_id 传 all（不分大小写）表示不限容器
_ALL_CONTAINERS = "all"


class AlertStore:
    """告警写入、查询与统计。"""

    def add_alert(
        self,
        output_fields: Dict[str, Any],
        category: str,
        reason: str,
        attribute_value: str = "",
    ):
        """写入单条未命中告警。"""
        try:
            row = alert_row(output_fields, category, reason, attribute_value)
            with self._write_cursor() as cursor:
                cursor.execute(_INSERT_SQL, row)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Alert stored container_id={row[0]} category={category} reason={reason}")
        except Exception as error:
            logger.error(f"Failed to add alert to storage: {error}")

    def add_alerts_batch(self, alerts_list: List[Dict[str, Any]]):
        """批量写入告警（摄取端使用）；空列表直接返回。"""
        if not alerts_list:
            return
        try:
            rows = [
                alert_row(
                    item.get("output_fields", {}),
                    item.get("category", "unknown"),
                    item.get("reason", ""),
                    item.get("attribute_value", ""),
                )
                for item in alerts_list
            ]
            with self._write_cursor() as cursor:
                execute_batch(cursor, _INSERT_SQL, rows)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Batch inserted {len(alerts_list)} alerts")
        except Exception as error:
            logger.error(f"Failed to add alerts batch to storage: {error}")

    def get_alerts(
        self,
        container_id: str,
        window_seconds: int = 0,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按容器与时间窗列出告警；window_seconds=0 表示不限窗口。"""
        try:
            conditions: List[str] = []
            params: List[Any] = []

            if container_id and container_id.lower() != _ALL_CONTAINERS:
                conditions.append("container_id = %s")
                params.append(container_id)

            if window_seconds and window_seconds > 0:
                conditions.append("timestamp >= %s")
                params.append(datetime.utcnow().timestamp() - window_seconds)

            query = _SELECT_COLUMNS
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            with self._read_cursor(dict_rows=True) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
            return [alert_entry(row) for row in rows]
        except Exception as error:
            logger.error(f"Failed to query alerts: {error}")
            return []

    def get_alert_stats(
        self,
        container_id: str,
        window_seconds: int = 300,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按告警类别聚合数量或速率，供总览页的分布图使用。

        给了时间窗时返回"每秒条数"，否则返回窗口内的原始条数。
        """
        try:
            use_time_filter = window_seconds is not None and window_seconds > 0
            start_ts = (datetime.utcnow().timestamp() - window_seconds) if use_time_filter else None
            query, params = self._stats_query(container_id, start_ts, priority, use_time_filter)

            with self._read_cursor(dict_rows=True) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

            return [
                {
                    "rule": row["category"] or "unknown",
                    "priority": row["priority"] or "unknown",
                    "rate": float(row["cnt"]) / float(window_seconds) if use_time_filter else float(row["cnt"]),
                }
                for row in rows
            ]
        except Exception as error:
            logger.error(f"Failed to query alert stats: {error}")
            return []

    @staticmethod
    def _stats_query(container_id: str, start_ts, priority, use_time_filter: bool):
        """拼出统计语句与参数：容器必选，时间窗与优先级可选。"""
        conditions = ["container_id = %s"]
        params: List[Any] = [container_id]

        if use_time_filter:
            conditions.append("timestamp >= %s")
            params.append(start_ts)

        if priority:
            conditions.append("priority = %s")
            params.append(priority)

        query = f"{_STATS_COLUMNS} WHERE {' AND '.join(conditions)} {_STATS_GROUPING}"
        return query, params
