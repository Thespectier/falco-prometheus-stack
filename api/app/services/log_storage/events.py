"""events 表：原始 Falco 事件的写入与分页查询。

写入有单条与批量两条路径：摄取端走批量（`execute_batch`），调试与回放走单条。
查询支持两种翻页方式——按 offset 分页，或带 `cursor_ts` 的游标式翻页（前端滚动
加载用后者，避免深分页）。
"""

from typing import Any, Dict, List, Optional

from psycopg2.extras import execute_batch

from .base import LOG_STORAGE_DEBUG, logger
from .values import event_row, log_entry

_INSERT_SQL = """
    INSERT INTO events (container_id, timestamp, rule, priority, source, output, tags, raw_event)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

_SELECT_COLUMNS = "SELECT timestamp, rule, priority, source, output, tags FROM events"

_SELECT_PAGE_SQL = f"""
    {_SELECT_COLUMNS}
    WHERE container_id = %s
    ORDER BY timestamp DESC
    LIMIT %s OFFSET %s
"""

_SELECT_BEFORE_TS_SQL = f"""
    {_SELECT_COLUMNS}
    WHERE container_id = %s AND timestamp < %s
    ORDER BY timestamp DESC
    LIMIT %s
"""


class EventStore:
    """事件写入与查询。"""

    def add_event(self, event: Dict[str, Any]):
        """写入单条事件。"""
        try:
            row = event_row(event)
            with self._write_cursor() as cursor:
                cursor.execute(_INSERT_SQL, row)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Event stored container_id={row[0]} timestamp={row[1]}")
        except Exception as error:
            logger.error(f"Failed to add event to storage: {error}")

    def add_event_batch(self, events: List[Dict[str, Any]]):
        """批量写入事件；空列表直接返回，不占用连接。"""
        if not events:
            return
        try:
            rows = [event_row(event) for event in events]
            with self._write_cursor() as cursor:
                execute_batch(cursor, _INSERT_SQL, rows)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Batch inserted {len(events)} events")
        except Exception as error:
            logger.error(f"Failed to add event batch to storage: {error}")

    def get_logs(
        self,
        container_id: str,
        limit: int = 100,
        offset: int = 0,
        cursor_ts: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """按容器取日志；给了 cursor_ts 就取该时刻之前的若干条。"""
        try:
            with self._read_cursor(dict_rows=True) as cursor:
                if cursor_ts:
                    cursor.execute(_SELECT_BEFORE_TS_SQL, (container_id, cursor_ts, limit))
                else:
                    cursor.execute(_SELECT_PAGE_SQL, (container_id, limit, offset))
                rows = cursor.fetchall()
            return [log_entry(row) for row in rows]
        except Exception as error:
            logger.error(f"Failed to query logs: {error}")
            return []
