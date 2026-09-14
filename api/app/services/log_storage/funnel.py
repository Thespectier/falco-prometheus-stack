"""漏斗统计：日志 → 告警 → 事件。

日志数取自 Prometheus 的事件总量，告警与事件数取自本地库。两段各自容错：取不到就
留 0，接口始终返回完整结构，前端不必处理缺字段。

计数查询逐表独立：某张表缺失或不可用只让该表的计数保持 0，不影响另一张表，因此这里
手写连接生命周期而不是用 `_read_cursor`——后者在语句失败时会直接报废连接。
"""

import os
from datetime import datetime
from typing import Dict, Tuple

import psycopg2

from .base import logger

# 镜像内的默认地址：exporter 由 compose 注入到 Prometheus 之前的这一跳
_DEFAULT_PROMETHEUS_URL = "http://43039infrasecurity-exporter:9090"
_PROMETHEUS_TIMEOUT_SECONDS = 2.0

# (统计键, 表名)
_COUNT_TABLES: Tuple[Tuple[str, str], ...] = (("alerts", "alerts"), ("incidents", "incidents"))


class FunnelStats:
    """漏斗统计。"""

    def get_funnel_stats(self, window_seconds: int = 0) -> Dict[str, int]:
        """返回日志、告警、事件三段的数量；window_seconds=0 表示全时段。"""
        stats = {"logs": 0, "alerts": 0, "incidents": 0}
        stats["logs"] = self._logs_count(window_seconds)
        stats.update(self._stored_counts(window_seconds))
        return stats

    @staticmethod
    def _logs_count(window_seconds: int) -> int:
        """从 Prometheus 取事件总量；窗口大于 0 时取增量。"""
        try:
            import httpx

            prometheus_url = os.getenv("PROMETHEUS_URL", _DEFAULT_PROMETHEUS_URL)
            if window_seconds > 0:
                query = f"sum(increase(syscall_events_total[{int(window_seconds)}s]))"
            else:
                query = "sum(syscall_events_total)"

            with httpx.Client(timeout=_PROMETHEUS_TIMEOUT_SECONDS) as client:
                response = client.get(f"{prometheus_url}/api/v1/query", params={"query": query})
                if response.status_code != 200:
                    return 0
                result = response.json().get("data", {}).get("result", [])
                if not result:
                    return 0
                return int(float(result[0].get("value", [0, 0])[1]))
        except Exception as error:
            logger.error(f"Failed to query Prometheus for logs count: {error}")
            return 0

    def _stored_counts(self, window_seconds: int) -> Dict[str, int]:
        """统计 alerts / incidents 两张表的行数。"""
        counts = {"alerts": 0, "incidents": 0}
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            for key, table in _COUNT_TABLES:
                try:
                    if window_seconds > 0:
                        start_ts = datetime.utcnow().timestamp() - window_seconds
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE timestamp >= %s", (start_ts,))
                    else:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row = cursor.fetchone()
                    if row:
                        counts[key] = row[0]
                except psycopg2.OperationalError:
                    # 单表不可用（缺表、权限不足）时保持 0，继续统计下一张
                    pass
            cursor.close()
            self.pool.putconn(conn)
        except Exception as error:
            logger.error(f"Failed to query alerts/incidents count: {error}")
            if conn:
                self.pool.putconn(conn, close=True)
        return counts
