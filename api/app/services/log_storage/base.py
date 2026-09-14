"""共用基础设施：日志器、连接池、建表与游标生命周期。

读路径用 `_read_cursor`（不提交），写路径用 `_write_cursor`（退出时提交）。两者在
语句或提交失败时都会以 `close=True` 归还连接再抛出异常，由各业务方法决定记日志
还是返回默认值。

建表语句集中在 `_SCHEMA_STATEMENTS`：新增列时改这一处，且必须保持
`IF NOT EXISTS` 语义，否则老库启动会直接失败。
"""

import logging
import os
from contextlib import contextmanager

from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("LogStorage")

# 打开后会把每次写入的容器/类目也记进日志，仅供排障
LOG_STORAGE_DEBUG = os.getenv("LOG_STORAGE_DEBUG", "0") == "1"

_DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/falco_data"

# 连接池上下限：摄取端是多线程批量写，读接口由请求驱动
_POOL_MIN_CONNECTIONS = 1
_POOL_MAX_CONNECTIONS = 20

_SCHEMA_STATEMENTS = (
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_container_ts ON events (container_id, timestamp DESC)",
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_container_ts ON alerts (container_id, timestamp DESC)",
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_incidents_container_ts ON incidents (container_id, timestamp DESC)",
    """
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,
)


class DatabaseBacked:
    """持有连接池的基类：建表 + 提供读写游标。"""

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)
        self.pool = None
        self._bootstrap()
        try:
            logger.info(f"LogStorage initialized with PG pool.")
        except Exception:
            pass

    def _bootstrap(self):
        """建连接池并把缺失的表/索引补齐。失败只记日志，不阻断进程启动。"""
        try:
            self.pool = pool.ThreadedConnectionPool(
                _POOL_MIN_CONNECTIONS, _POOL_MAX_CONNECTIONS, self.db_url
            )
            conn = self.pool.getconn()
            cursor = conn.cursor()
            for statement in _SCHEMA_STATEMENTS:
                cursor.execute(statement)
            conn.commit()
            cursor.close()
            self.pool.putconn(conn)
        except Exception as error:
            logger.error(f"Failed to initialize PostgreSQL database: {error}")

    @contextmanager
    def _read_cursor(self, dict_rows: bool = False):
        """读游标：不提交；异常时关闭连接并原样抛出。"""
        conn = self.pool.getconn()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if dict_rows else conn.cursor()
        try:
            yield cursor
        except Exception:
            self.pool.putconn(conn, close=True)
            raise
        else:
            cursor.close()
            self.pool.putconn(conn)

    @contextmanager
    def _write_cursor(self, dict_rows: bool = False):
        """写游标：语句执行完提交；提交失败同样关闭连接再抛出。"""
        conn = self.pool.getconn()
        cursor = conn.cursor(cursor_factory=RealDictCursor) if dict_rows else conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            self.pool.putconn(conn, close=True)
            raise
        else:
            cursor.close()
            self.pool.putconn(conn)
