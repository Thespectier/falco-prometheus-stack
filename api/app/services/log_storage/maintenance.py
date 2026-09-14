"""过期数据清理与库维护。

保留期由调用方（reducer 的定时任务）按环境变量算出后传入。这里只做删除与计数，
不归档、不压缩——需要历史数据时应从上游采集端留存，而不是拉长库内保留期。
"""

from datetime import datetime

from .base import logger

_SECONDS_PER_DAY = 86400


class Maintenance:
    """清理与维护。"""

    def cleanup_old_data(self, retention_days: float = 0.25):
        """删除 events 表中超过保留期的行。"""
        try:
            cutoff_ts = datetime.utcnow().timestamp() - (retention_days * _SECONDS_PER_DAY)
            with self._write_cursor() as cursor:
                cursor.execute("DELETE FROM events WHERE timestamp < %s", (cutoff_ts,))
                deleted_events = cursor.rowcount
            if deleted_events > 0:
                logger.info(f"Cleanup completed. Deleted events: {deleted_events}")
        except Exception as error:
            logger.error(f"Failed to cleanup events: {error}")

    def cleanup_old_alerts(self, retention_days: float = 0.125):
        """删除 alerts 表中超过保留期的行。"""
        try:
            cutoff_ts = datetime.utcnow().timestamp() - (retention_days * _SECONDS_PER_DAY)
            with self._write_cursor() as cursor:
                cursor.execute("DELETE FROM alerts WHERE timestamp < %s", (cutoff_ts,))
                deleted_alerts = cursor.rowcount
            if deleted_alerts > 0:
                logger.info(f"Alerts cleanup completed. Deleted alerts: {deleted_alerts}")
        except Exception as error:
            logger.error(f"Failed to cleanup alerts: {error}")

    def vacuum_logs_db(self):
        """占位接口：VACUUM 交给 PostgreSQL 的 autovacuum 守护进程。"""
        logger.info("VACUUM is managed by PostgreSQL autovacuum daemon automatically.")
