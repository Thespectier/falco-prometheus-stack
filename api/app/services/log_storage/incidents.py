"""incidents 表：归约产出的安全事件，以及分析服务回填的结论。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import LOG_STORAGE_DEBUG, logger
from .values import incident_entry

_INSERT_SQL = """
    INSERT INTO incidents (
        container_id, timestamp, threat_score, cluster_id, attribute_name, attribute_value,
        event_type, process_name, alert_content, details, analysis_window, similarity_threshold, created_at, analysis
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_SELECT_COLUMNS = """
    SELECT id, container_id, timestamp, threat_score, cluster_id, attribute_name, attribute_value,
           event_type, process_name, alert_content, details, analysis_window, similarity_threshold, created_at, analysis
    FROM incidents
"""

_UPDATE_ANALYSIS_SQL = "UPDATE incidents SET analysis = %s WHERE id = %s"


class IncidentStore:
    """事件写入与查询。"""

    def add_incident(
        self,
        *,
        container_id: str,
        timestamp: float,
        threat_score: float,
        cluster_id: int | None,
        attribute_name: str | None,
        attribute_value: str | None,
        event_type: str | None,
        process_name: str | None,
        alert_content: str | None,
        details: str | None,
        analysis_window: int | None = 300,
        similarity_threshold: float | None = 0.8,
        analysis: str | None = None,
    ) -> None:
        """写入一条事件；字段全部走关键字参数，避免长位置参数列表错位。"""
        try:
            created_at = datetime.utcnow().timestamp()
            with self._write_cursor() as cursor:
                cursor.execute(
                    _INSERT_SQL,
                    (
                        str(container_id),
                        float(timestamp),
                        float(threat_score),
                        cluster_id,
                        attribute_name,
                        attribute_value,
                        event_type,
                        process_name,
                        alert_content,
                        details,
                        analysis_window,
                        similarity_threshold,
                        created_at,
                        analysis,
                    ),
                )
            if LOG_STORAGE_DEBUG:
                logger.info(
                    f"Incident stored container_id={container_id} score={threat_score} cluster={cluster_id}"
                )
        except Exception as error:
            logger.error(f"Failed to add incident to storage: {error}")

    def update_incident_analysis(self, incident_id: int, analysis: str):
        """回填某条事件的分析结论。"""
        try:
            with self._write_cursor() as cursor:
                cursor.execute(_UPDATE_ANALYSIS_SQL, (analysis, incident_id))
            if LOG_STORAGE_DEBUG:
                logger.info(f"Updated analysis for incident {incident_id}")
        except Exception as error:
            logger.error(f"Failed to update incident analysis: {error}")

    def get_incidents(
        self,
        container_id: Optional[str] = None,
        window_seconds: int = 0,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出事件；容器与时间窗都是可选过滤条件。"""
        try:
            conditions: List[str] = []
            params: List[Any] = []

            if container_id:
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
            return [incident_entry(row) for row in rows]
        except Exception as error:
            logger.error(f"Failed to query incidents: {error}")
            return []
