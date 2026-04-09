import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, execute_batch

logger = logging.getLogger("LogStorage")
LOG_STORAGE_DEBUG = os.getenv("LOG_STORAGE_DEBUG", "0") == "1"

class LogStorage:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/falco_data")
        self.pool = None
        self._init_db()
        try:
            logger.info(f"LogStorage initialized with PG pool.")
        except Exception:
            pass

    def _init_db(self):
        try:
            # Create a thread-safe connection pool
            self.pool = pool.ThreadedConnectionPool(1, 20, self.db_url)
            
            conn = self.pool.getconn()
            cursor = conn.cursor()
            
            # Create events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL,
                    rule TEXT,
                    priority TEXT,
                    source TEXT,
                    output JSONB,
                    tags JSONB,
                    raw_event JSONB
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_container_ts ON events (container_id, timestamp DESC)')

            # Create alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL,
                    category TEXT,
                    priority TEXT,
                    reason TEXT,
                    evt_type TEXT,
                    proc_name TEXT,
                    fd_name TEXT,
                    output JSONB,
                    attribute_value TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_container_ts ON alerts (container_id, timestamp DESC)')

            # Create incidents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS incidents (
                    id SERIAL PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL,
                    threat_score DOUBLE PRECISION NOT NULL,
                    cluster_id INTEGER,
                    attribute_name TEXT,
                    attribute_value TEXT,
                    event_type TEXT,
                    process_name TEXT,
                    alert_content TEXT,
                    details TEXT,
                    analysis_window INTEGER,
                    similarity_threshold DOUBLE PRECISION,
                    created_at DOUBLE PRECISION NOT NULL,
                    analysis TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_container_ts ON incidents (container_id, timestamp DESC)')
            
            # Create config table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL database: {e}")

    def get_config(self, key: str) -> Optional[str]:
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = %s", (key,))
            row = cursor.fetchone()
            cursor.close()
            self.pool.putconn(conn)
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get config {key}: {e}")
            if conn: self.pool.putconn(conn, close=True)
            return None

    def set_config(self, key: str, value: str):
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO config (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            ''', (key, value))
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Set config {key}")
        except Exception as e:
            logger.error(f"Failed to set config {key}: {e}")
            if conn: self.pool.putconn(conn, close=True)

    def _prepare_event_tuple(self, event: Dict[str, Any]):
        output_fields = event.get('output_fields', {})
        container_id = (
            output_fields.get('container.name')
            or output_fields.get('container.id')
            or output_fields.get('k8s.pod.name')
            or event.get('hostname')
            or 'unknown'
        )
        if not container_id:
            container_id = 'unknown'
        container_id = str(container_id)
        
        ts_val = event.get('time') or output_fields.get('evt.time') or output_fields.get('evt.time.iso8601')
        if isinstance(ts_val, str):
             try:
                 dt = datetime.fromisoformat(ts_val.replace('Z', '+00:00'))
                 timestamp = dt.timestamp()
             except:
                 timestamp = datetime.utcnow().timestamp()
        elif isinstance(ts_val, (int, float)):
             timestamp = ts_val if ts_val < 1e11 else ts_val / 1e9
        else:
             timestamp = datetime.utcnow().timestamp()

        rule = event.get('rule', 'unknown')
        priority = event.get('priority', 'unknown')
        source = event.get('source', 'unknown')
        output = json.dumps(output_fields, ensure_ascii=False)
        tags = json.dumps(event.get('tags', []))
        raw = json.dumps(event)
        
        return (container_id, timestamp, rule, priority, source, output, tags, raw)

    def add_event(self, event: Dict[str, Any]):
        try:
            val = self._prepare_event_tuple(event)
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (container_id, timestamp, rule, priority, source, output, tags, raw_event)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', val)
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                try:
                    logger.info(f"Event stored container_id={val[0]} timestamp={val[1]}")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to add event to storage: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def add_event_batch(self, events: List[Dict[str, Any]]):
        if not events:
            return
        try:
            vals = [self._prepare_event_tuple(e) for e in events]
            conn = self.pool.getconn()
            cursor = conn.cursor()
            execute_batch(cursor, '''
                INSERT INTO events (container_id, timestamp, rule, priority, source, output, tags, raw_event)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', vals)
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Batch inserted {len(events)} events")
        except Exception as e:
            logger.error(f"Failed to add event batch to storage: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def get_logs(self, container_id: str, limit: int = 100, offset: int = 0, cursor_ts: Optional[float] = None) -> List[Dict[str, Any]]:
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if cursor_ts:
                cursor.execute('''
                    SELECT timestamp, rule, priority, source, output, tags 
                    FROM events 
                    WHERE container_id = %s AND timestamp < %s
                    ORDER BY timestamp DESC 
                    LIMIT %s
                ''', (container_id, cursor_ts, limit))
            else:
                cursor.execute('''
                    SELECT timestamp, rule, priority, source, output, tags 
                    FROM events 
                    WHERE container_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s OFFSET %s
                ''', (container_id, limit, offset))
            
            rows = cursor.fetchall()
            cursor.close()
            self.pool.putconn(conn)
            
            logs = []
            for row in rows:
                logs.append({
                    "timestamp": datetime.fromtimestamp(row['timestamp'] + 8 * 3600).isoformat(),
                    "rule": row['rule'],
                    "priority": row['priority'],
                    "source": row['source'],
                    "output": json.dumps(row['output']) if isinstance(row['output'], dict) else row['output'],
                    "tags": row['tags'] if isinstance(row['tags'], list) else (json.loads(row['tags']) if row['tags'] else [])
                })
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)
            return []

    def _prepare_alert_tuple(self, output_fields: Dict[str, Any], category: str, reason: str, attribute_value: str = ""):
        container_id = (
            output_fields.get('container.name')
            or output_fields.get('container.id')
            or output_fields.get('k8s.pod.name')
            or 'unknown'
        )
        container_id = str(container_id)

        ts_val = output_fields.get('evt.time') or output_fields.get('evt.time.iso8601')
        if isinstance(ts_val, str):
            try:
                dt = datetime.fromisoformat(ts_val.replace('Z', '+00:00'))
                timestamp = dt.timestamp()
            except:
                timestamp = datetime.utcnow().timestamp()
        elif isinstance(ts_val, (int, float)):
            timestamp = ts_val if ts_val < 1e11 else ts_val / 1e9
        else:
            timestamp = datetime.utcnow().timestamp()

        priority = 'Warning'
        evt_type = output_fields.get('evt.type', '')
        proc_name = output_fields.get('proc.name', '')
        fd_name = output_fields.get('fd.name', '')
        output = json.dumps(output_fields, ensure_ascii=False)

        return (container_id, timestamp, category, priority, reason, evt_type, proc_name, fd_name, output, attribute_value)

    def add_alert(self, output_fields: Dict[str, Any], category: str, reason: str, attribute_value: str = ""):
        try:
            val = self._prepare_alert_tuple(output_fields, category, reason, attribute_value)
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts (container_id, timestamp, category, priority, reason, evt_type, proc_name, fd_name, output, attribute_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', val)
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                try:
                    logger.info(f"Alert stored container_id={val[0]} category={category} reason={reason}")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to add alert to storage: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def add_alerts_batch(self, alerts_list: List[Dict[str, Any]]):
        if not alerts_list:
            return
        try:
            vals = [
                self._prepare_alert_tuple(
                    item.get("output_fields", {}),
                    item.get("category", "unknown"),
                    item.get("reason", ""),
                    item.get("attribute_value", "")
                )
                for item in alerts_list
            ]
            conn = self.pool.getconn()
            cursor = conn.cursor()
            execute_batch(cursor, '''
                INSERT INTO alerts (container_id, timestamp, category, priority, reason, evt_type, proc_name, fd_name, output, attribute_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', vals)
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Batch inserted {len(alerts_list)} alerts")
        except Exception as e:
            logger.error(f"Failed to add alerts batch to storage: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

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
        try:
            now_ts = datetime.utcnow().timestamp()
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO incidents (
                    container_id, timestamp, threat_score, cluster_id, attribute_name, attribute_value,
                    event_type, process_name, alert_content, details, analysis_window, similarity_threshold, created_at, analysis
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    str(container_id), float(timestamp), float(threat_score), cluster_id,
                    attribute_name, attribute_value, event_type, process_name,
                    alert_content, details, analysis_window, similarity_threshold, now_ts, analysis
                )
            )
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                try:
                    logger.info(
                        f"Incident stored container_id={container_id} score={threat_score} cluster={cluster_id}"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to add incident to storage: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def update_incident_analysis(self, incident_id: int, analysis: str):
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE incidents SET analysis = %s WHERE id = %s",
                (analysis, incident_id)
            )
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if LOG_STORAGE_DEBUG:
                logger.info(f"Updated analysis for incident {incident_id}")
        except Exception as e:
            logger.error(f"Failed to update incident analysis: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def get_incidents(
        self,
        container_id: Optional[str] = None,
        window_seconds: int = 0,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            base = '''
                SELECT id, container_id, timestamp, threat_score, cluster_id, attribute_name, attribute_value,
                       event_type, process_name, alert_content, details, analysis_window, similarity_threshold, created_at, analysis
                FROM incidents
            '''
            params: list[Any] = []
            where: list[str] = []
            if container_id:
                where.append('container_id = %s')
                params.append(container_id)
            if window_seconds and window_seconds > 0:
                now_ts = datetime.utcnow().timestamp()
                start_ts = now_ts - window_seconds
                where.append('timestamp >= %s')
                params.append(start_ts)
            if where:
                base += ' WHERE ' + ' AND '.join(where)
            base += ' ORDER BY timestamp DESC LIMIT %s OFFSET %s'
            params.extend([limit, offset])
            cursor.execute(base, params)
            rows = cursor.fetchall()
            cursor.close()
            self.pool.putconn(conn)
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "container_id": r["container_id"],
                    "timestamp": datetime.fromtimestamp(r["timestamp"] + 8 * 3600).isoformat(),
                    "threat_score": r["threat_score"],
                    "cluster_id": r["cluster_id"],
                    "attribute_name": r["attribute_name"],
                    "attribute_value": r["attribute_value"],
                    "event_type": r["event_type"],
                    "process_name": r["process_name"],
                    "alert_content": r["alert_content"],
                    "details": r["details"],
                    "analysis_window": r["analysis_window"],
                    "similarity_threshold": r["similarity_threshold"],
                    "created_at": datetime.fromtimestamp(r["created_at"] + 8 * 3600).isoformat(),
                    "analysis": r["analysis"],
                })
            return items
        except Exception as e:
            logger.error(f"Failed to query incidents: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)
            return []

    def get_funnel_stats(self, window_seconds: int = 0) -> Dict[str, int]:
        try:
            stats = {"logs": 0, "alerts": 0, "incidents": 0}
            
            # 1. Query Logs count from Prometheus
            try:
                import httpx
                prometheus_url = os.getenv("PROMETHEUS_URL", "http://43039infrasecurity-exporter:9090")
                
                if window_seconds > 0:
                    duration_str = f"{int(window_seconds)}s"
                    query = f'sum(increase(syscall_events_total[{duration_str}]))'
                else:
                    query = 'sum(syscall_events_total)'
                    
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(f"{prometheus_url}/api/v1/query", params={"query": query})
                    if resp.status_code == 200:
                        data = resp.json()
                        result = data.get("data", {}).get("result", [])
                        if result:
                            stats["logs"] = int(float(result[0].get("value", [0, 0])[1]))
            except Exception as e:
                logger.error(f"Failed to query Prometheus for logs count: {e}")

            # 2. Query Postgres DB for alerts and incidents
            try:
                conn = self.pool.getconn()
                cursor = conn.cursor()
                
                tables = {"alerts": "alerts", "incidents": "incidents"}
                for key, table in tables.items():
                    try:
                        if window_seconds > 0:
                            start_ts = datetime.utcnow().timestamp() - window_seconds
                            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE timestamp >= %s", (start_ts,))
                        else:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row = cursor.fetchone()
                        if row:
                            stats[key] = row[0]
                    except psycopg2.OperationalError:
                        pass
                cursor.close()
                self.pool.putconn(conn)
            except Exception as e:
                logger.error(f"Failed to query alerts/incidents count: {e}")
                if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                    self.pool.putconn(conn, close=True)
                
            return stats
        except Exception as e:
            logger.error(f"Failed to get funnel stats: {e}")
            return {"logs": 0, "alerts": 0, "incidents": 0}

    def get_alert_stats(self, container_id: str, window_seconds: int = 300, priority: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            now_ts = datetime.utcnow().timestamp()
            use_time_filter = window_seconds is not None and window_seconds > 0
            start_ts = (now_ts - window_seconds) if use_time_filter else None
            conn = self.pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            if priority and use_time_filter:
                cursor.execute('''
                    SELECT category, priority, COUNT(*) as cnt
                    FROM alerts
                    WHERE container_id = %s AND timestamp >= %s AND priority = %s
                    GROUP BY category, priority
                ''', (container_id, start_ts, priority))
            elif priority and not use_time_filter:
                cursor.execute('''
                    SELECT category, priority, COUNT(*) as cnt
                    FROM alerts
                    WHERE container_id = %s AND priority = %s
                    GROUP BY category, priority
                ''', (container_id, priority))
            else:
                if use_time_filter:
                    cursor.execute('''
                        SELECT category, priority, COUNT(*) as cnt
                        FROM alerts
                        WHERE container_id = %s AND timestamp >= %s
                        GROUP BY category, priority
                    ''', (container_id, start_ts))
                else:
                    cursor.execute('''
                        SELECT category, priority, COUNT(*) as cnt
                        FROM alerts
                        WHERE container_id = %s
                        GROUP BY category, priority
                    ''', (container_id,))

            rows = cursor.fetchall()
            cursor.close()
            self.pool.putconn(conn)

            stats = []
            for row in rows:
                rate = float(row['cnt']) / float(window_seconds) if use_time_filter else float(row['cnt'])
                stats.append({
                    'rule': row['category'] or 'unknown',
                    'priority': row['priority'] or 'unknown',
                    'rate': rate
                })
            return stats
        except Exception as e:
            logger.error(f"Failed to query alert stats: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)
            return []

    def get_alerts(self, container_id: str, window_seconds: int = 0, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            base_query = '''
                SELECT container_id, timestamp, category, reason, evt_type, proc_name, fd_name, output, attribute_value
                FROM alerts
            '''
            params = []
            where_clauses = []

            if container_id and container_id.lower() != 'all':
                where_clauses.append("container_id = %s")
                params.append(container_id)

            if window_seconds and window_seconds > 0:
                now_ts = datetime.utcnow().timestamp()
                start_ts = now_ts - window_seconds
                where_clauses.append("timestamp >= %s")
                params.append(start_ts)

            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)

            base_query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cursor.execute(base_query, params)
            rows = cursor.fetchall()
            cursor.close()
            self.pool.putconn(conn)
            
            items = []
            for r in rows:
                items.append({
                    "container_id": r["container_id"],
                    "timestamp": datetime.fromtimestamp(r["timestamp"] + 8 * 3600).isoformat(),
                    "category": r["category"],
                    "reason": r["reason"],
                    "evt_type": r["evt_type"],
                    "proc_name": r["proc_name"],
                    "fd_name": r["fd_name"],
                    "output": json.dumps(r["output"]) if isinstance(r["output"], dict) else r["output"],
                    "attribute_value": r["attribute_value"],
                })
            return items
        except Exception as e:
            logger.error(f"Failed to query alerts: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)
            return []

    def cleanup_old_data(self, retention_days: float = 0.25):
        try:
            cutoff_ts = datetime.utcnow().timestamp() - (retention_days * 86400)
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE timestamp < %s", (cutoff_ts,))
            deleted_events = cursor.rowcount
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if deleted_events > 0:
                logger.info(f"Cleanup completed. Deleted events: {deleted_events}")
        except Exception as e:
            logger.error(f"Failed to cleanup events: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def cleanup_old_alerts(self, retention_days: float = 0.125):
        try:
            cutoff_ts = datetime.utcnow().timestamp() - (retention_days * 86400)
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alerts WHERE timestamp < %s", (cutoff_ts,))
            deleted_alerts = cursor.rowcount
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
            if deleted_alerts > 0:
                logger.info(f"Alerts cleanup completed. Deleted alerts: {deleted_alerts}")
        except Exception as e:
            logger.error(f"Failed to cleanup alerts: {e}")
            if hasattr(self, 'pool') and self.pool and 'conn' in locals() and conn:
                self.pool.putconn(conn, close=True)

    def vacuum_logs_db(self):
        logger.info("VACUUM is managed by PostgreSQL autovacuum daemon automatically.")

log_storage = LogStorage()