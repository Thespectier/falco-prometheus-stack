import sqlite3
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("LogStorage")
LOG_STORAGE_DEBUG = os.getenv("LOG_STORAGE_DEBUG", "0") == "1"

class LogStorage:
    def __init__(self, db_path: str = "data/logs.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        try:
            logger.info(f"LogStorage initialized at {self.db_path}")
        except Exception:
            pass

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create events table
            # We index container_id and timestamp for faster queries
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    rule TEXT,
                    priority TEXT,
                    source TEXT,
                    output TEXT,
                    tags TEXT,
                    raw_event TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_container_ts ON events (container_id, timestamp DESC)')

            # Create alerts table for Hanabi detection-phase mismatches
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    category TEXT,
                    priority TEXT,
                    reason TEXT,
                    evt_type TEXT,
                    proc_name TEXT,
                    fd_name TEXT,
                    output TEXT,
                    attribute_value TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_container_ts ON alerts (container_id, timestamp DESC)')

            # Migration: Add attribute_value column if not exists
            try:
                cursor.execute("SELECT attribute_value FROM alerts LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE alerts ADD COLUMN attribute_value TEXT")
                logger.info("Migrated alerts table: added attribute_value column")

            # Create incidents table for reduced alerts (post-reducer)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    threat_score REAL NOT NULL,
                    cluster_id INTEGER,
                    attribute_name TEXT,
                    attribute_value TEXT,
                    event_type TEXT,
                    process_name TEXT,
                    alert_content TEXT,
                    details TEXT,
                    analysis_window INTEGER,
                    similarity_threshold REAL,
                    created_at REAL NOT NULL,
                    analysis TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_container_ts ON incidents (container_id, timestamp DESC)')
            
            # Create config table for dynamic settings (e.g. LLM config)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # Migration: Add analysis column if not exists
            try:
                cursor.execute("SELECT analysis FROM incidents LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE incidents ADD COLUMN analysis TEXT")
                logger.info("Migrated incidents table: added analysis column")

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def get_config(self, key: str) -> Optional[str]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get config {key}: {e}")
            return None

    def set_config(self, key: str, value: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            conn.close()
            if LOG_STORAGE_DEBUG:
                logger.info(f"Set config {key}")
        except Exception as e:
            logger.error(f"Failed to set config {key}: {e}")

    def add_event(self, event: Dict[str, Any]):
        try:
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
            
            # Parse timestamp
            ts_val = event.get('time') or output_fields.get('evt.time') or output_fields.get('evt.time.iso8601')
            if isinstance(ts_val, str):
                 # Try parsing ISO format if needed, but usually it comes as string from Falco
                 # For simplicity, use current time if parsing fails or rely on 'evt.time' if it's epoch
                 try:
                     dt = datetime.fromisoformat(ts_val.replace('Z', '+00:00'))
                     timestamp = dt.timestamp()
                 except:
                     timestamp = datetime.utcnow().timestamp()
            elif isinstance(ts_val, (int, float)):
                 timestamp = ts_val if ts_val < 1e11 else ts_val / 1e9 # handle ns
            else:
                 timestamp = datetime.utcnow().timestamp()

            rule = event.get('rule', 'unknown')
            priority = event.get('priority', 'unknown')
            source = event.get('source', 'unknown')
            output = json.dumps(output_fields, ensure_ascii=False)
            tags = json.dumps(event.get('tags', []))
            raw = json.dumps(event)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (container_id, timestamp, rule, priority, source, output, tags, raw_event)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (container_id, timestamp, rule, priority, source, output, tags, raw))
            
            conn.commit()
            conn.close()
            if LOG_STORAGE_DEBUG:
                try:
                    logger.info(f"Event stored container_id={container_id} timestamp={timestamp} db={self.db_path}")
                except Exception:
                    pass
            
        except Exception as e:
            logger.error(f"Failed to add event to storage: {e}")

    def get_logs(self, container_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, rule, priority, source, output, tags 
                FROM events 
                WHERE container_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (container_id, limit, offset))
            
            rows = cursor.fetchall()
            conn.close()
            
            logs = []
            for row in rows:
                logs.append({
                    "timestamp": datetime.fromtimestamp(row['timestamp'] + 8 * 3600).isoformat(),
                    "rule": row['rule'],
                    "priority": row['priority'],
                    "source": row['source'],
                    "output": row['output'],
                    "tags": json.loads(row['tags']) if row['tags'] else []
                })
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return []


    def add_alert(self, output_fields: Dict[str, Any], category: str, reason: str, attribute_value: str = ""):
        try:
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

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts (container_id, timestamp, category, priority, reason, evt_type, proc_name, fd_name, output, attribute_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (container_id, timestamp, category, priority, reason, evt_type, proc_name, fd_name, output, attribute_value))
            conn.commit()
            conn.close()
            if LOG_STORAGE_DEBUG:
                try:
                    logger.info(f"Alert stored container_id={container_id} category={category} reason={reason}")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to add alert to storage: {e}")

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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO incidents (
                    container_id, timestamp, threat_score, cluster_id, attribute_name, attribute_value,
                    event_type, process_name, alert_content, details, analysis_window, similarity_threshold, created_at, analysis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(container_id), float(timestamp), float(threat_score), cluster_id,
                    attribute_name, attribute_value, event_type, process_name,
                    alert_content, details, analysis_window, similarity_threshold, now_ts, analysis
                )
            )
            conn.commit()
            conn.close()
            if LOG_STORAGE_DEBUG:
                try:
                    logger.info(
                        f"Incident stored container_id={container_id} score={threat_score} cluster={cluster_id}"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to add incident to storage: {e}")

    def update_incident_analysis(self, incident_id: int, analysis: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE incidents SET analysis = ? WHERE id = ?",
                (analysis, incident_id)
            )
            conn.commit()
            conn.close()
            if LOG_STORAGE_DEBUG:
                logger.info(f"Updated analysis for incident {incident_id}")
        except Exception as e:
            logger.error(f"Failed to update incident analysis: {e}")

    def get_incidents(
        self,
        container_id: Optional[str] = None,
        window_seconds: int = 0,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            base = '''
                SELECT id, container_id, timestamp, threat_score, cluster_id, attribute_name, attribute_value,
                       event_type, process_name, alert_content, details, analysis_window, similarity_threshold, created_at, analysis
                FROM incidents
            '''
            params: list[Any] = []
            where: list[str] = []
            if container_id:
                where.append('container_id = ?')
                params.append(container_id)
            if window_seconds and window_seconds > 0:
                now_ts = datetime.utcnow().timestamp()
                start_ts = now_ts - window_seconds
                where.append('timestamp >= ?')
                params.append(start_ts)
            if where:
                base += ' WHERE ' + ' AND '.join(where)
            base += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            cursor.execute(base, params)
            rows = cursor.fetchall()
            conn.close()
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
            return []

    def get_funnel_stats(self, window_seconds: int = 0) -> Dict[str, int]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {"logs": 0, "alerts": 0, "incidents": 0}
            tables = {"logs": "events", "alerts": "alerts", "incidents": "incidents"}
            
            if window_seconds > 0:
                now_ts = datetime.utcnow().timestamp()
                start_ts = now_ts - window_seconds
                for key, table in tables.items():
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE timestamp >= ?", (start_ts,))
                        row = cursor.fetchone()
                        if row:
                            stats[key] = row[0]
                    except sqlite3.OperationalError:
                        # Table might not exist
                        stats[key] = 0
            else:
                for key, table in tables.items():
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row = cursor.fetchone()
                        if row:
                            stats[key] = row[0]
                    except sqlite3.OperationalError:
                        stats[key] = 0
                    
            conn.close()
            return stats
        except Exception as e:
            logger.error(f"Failed to get funnel stats: {e}")
            return {"logs": 0, "alerts": 0, "incidents": 0}

    def get_alert_stats(self, container_id: str, window_seconds: int = 300, priority: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            now_ts = datetime.utcnow().timestamp()
            use_time_filter = window_seconds is not None and window_seconds > 0
            start_ts = (now_ts - window_seconds) if use_time_filter else None
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if priority and use_time_filter:
                cursor.execute('''
                    SELECT category, priority, COUNT(*) as cnt
                    FROM alerts
                    WHERE container_id = ? AND timestamp >= ? AND priority = ?
                    GROUP BY category, priority
                ''', (container_id, start_ts, priority))
            elif priority and not use_time_filter:
                cursor.execute('''
                    SELECT category, priority, COUNT(*) as cnt
                    FROM alerts
                    WHERE container_id = ? AND priority = ?
                    GROUP BY category, priority
                ''', (container_id, priority))
            else:
                if use_time_filter:
                    cursor.execute('''
                        SELECT category, priority, COUNT(*) as cnt
                        FROM alerts
                        WHERE container_id = ? AND timestamp >= ?
                        GROUP BY category, priority
                    ''', (container_id, start_ts))
                else:
                    cursor.execute('''
                        SELECT category, priority, COUNT(*) as cnt
                        FROM alerts
                        WHERE container_id = ?
                        GROUP BY category, priority
                    ''', (container_id,))

            rows = cursor.fetchall()
            conn.close()

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
            return []

# Detailed alerts query
    def get_alerts(self, container_id: str, window_seconds: int = 0, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if window_seconds and window_seconds > 0:
                now_ts = datetime.utcnow().timestamp()
                start_ts = now_ts - window_seconds
                cursor.execute('''
                    SELECT container_id, timestamp, category, reason, evt_type, proc_name, fd_name, output, attribute_value
                    FROM alerts
                    WHERE container_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                ''', (container_id, start_ts, limit, offset))
            else:
                cursor.execute('''
                    SELECT container_id, timestamp, category, reason, evt_type, proc_name, fd_name, output, attribute_value
                    FROM alerts
                    WHERE container_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                ''', (container_id, limit, offset))
            rows = cursor.fetchall()
            conn.close()
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
                    "output": r["output"],
                    "attribute_value": r["attribute_value"],
                })
            return items
        except Exception as e:
            logger.error(f"Failed to query alerts: {e}")
            return []
# Global instance
# Ensure the data directory exists
# Use a path relative to the project root for local development, or /app/data for Docker
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True) 

log_storage = LogStorage(db_path=os.path.join(DATA_DIR, "logs.db"))
