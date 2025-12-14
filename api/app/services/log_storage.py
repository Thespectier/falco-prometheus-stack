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
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

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
                    "timestamp": datetime.fromtimestamp(row['timestamp']).isoformat(),
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

# Global instance
# Ensure the data directory exists
# Use a path relative to the project root for local development, or /app/data for Docker
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True) 

log_storage = LogStorage(db_path=os.path.join(DATA_DIR, "logs.db"))
