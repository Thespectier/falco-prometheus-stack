"""log_storage 黄金输出验证。

用途：对 `api/app/services/log_storage` 做结构重构前后各运行一次，两次输出必须
一致（唯二允许的差异见文件末尾说明）。

本机没有 PostgreSQL / psycopg2 / httpx，因此用桩件替换：

  * `psycopg2`（含 `pool.ThreadedConnectionPool`、`extras.RealDictCursor`、
    `extras.execute_batch`、`OperationalError`）
  * `httpx.Client`（get_funnel_stats 里查 Prometheus 计数用）
  * `datetime.utcnow()` 固定到一个确定时刻，消除时间抖动

被验证的内容：

  * 建表/建索引的 DDL（表名、列名、索引名）
  * 每次查询执行的 **SQL（空白归一化后）与参数列表**
  * 连接池的取用/归还顺序，以及出错时是否带 close=True 归还
  * 每个公开方法的返回值、异常
  * 日志记录（级别 + 正文），包括错误路径

允许的差异（重构时有意修正的缺陷）：
  `get_config` / `set_config` 在 `pool.getconn()` 失败时，原实现会在 except 块里
  引用未绑定的局部变量 `conn` 而抛 UnboundLocalError；重构后按其余方法的既有语义
  返回默认值。除此之外不允许出现任何差异。

运行：python .dsh/verify/log_storage_golden.py <输出文件>
"""

import datetime as real_datetime
import io
import json
import logging
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

FIXED_UTC = real_datetime.datetime(2024, 5, 1, 12, 0, 0)
DATABASE_URL = "postgresql://u:p@db:5432/testdb"
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["PROMETHEUS_URL"] = "http://prometheus.test:9090"
os.environ["LOG_STORAGE_DEBUG"] = "0"

CALLS = []
LOG_RECORDS = []


def record(kind, **payload):
    CALLS.append({"call": kind, **payload})


def normalized(sql):
    return " ".join(str(sql).split())


def normalized_params(params):
    if params is None:
        return None
    if isinstance(params, (list, tuple)):
        return [normalized_params(item) for item in params]
    if isinstance(params, dict):
        return {key: normalized_params(value) for key, value in sorted(params.items())}
    if isinstance(params, float):
        return round(params, 6)
    return params


PLAN = {"rows": [], "rowcount": 0}


# ----------------------------------------------------------------- psycopg2 桩
class OperationalError(Exception):
    pass


class InterfaceError(Exception):
    pass


class _FakeCursor:
    def __init__(self, host):
        self.host = host
        self.factory_name = host.factory_name
        self.rowcount = 0

    def execute(self, sql, params=None):
        record(
            "execute",
            factory=self.factory_name,
            sql=normalized(sql),
            params=normalized_params(params),
        )
        if self.host.fail_execute:
            raise OperationalError("server closed the connection unexpectedly")
        self.rowcount = PLAN["rowcount"]

    def fetchall(self):
        return list(PLAN["rows"])

    def fetchone(self):
        return PLAN["rows"][0] if PLAN["rows"] else None

    def close(self):
        record("cursor.close")


class _FakeConn:
    def __init__(self):
        self.factory_name = None
        self.fail_execute = False

    def cursor(self, cursor_factory=None):
        self.factory_name = getattr(cursor_factory, "__name__", None)
        record("conn.cursor", factory=self.factory_name)
        return _FakeCursor(self)

    def commit(self):
        record("conn.commit")


class _FakePool:
    def __init__(self, minconn, maxconn, url):
        record("pool.created", minconn=minconn, maxconn=maxconn, url=url)
        self.mode = "ok"
        self.fail_execute = False

    def getconn(self):
        record("pool.getconn")
        if self.mode == "fail":
            raise OperationalError("connection pool is closed")
        conn = _FakeConn()
        conn.fail_execute = self.fail_execute
        return conn

    def putconn(self, conn, close=False):
        record("pool.putconn", close=bool(close))

    def closeall(self):
        record("pool.closeall")


class RealDictCursor:
    pass


def execute_batch(cursor, sql, values):
    record("execute_batch", sql=normalized(sql), count=len(values), params=normalized_params(values))


psycopg2_module = types.ModuleType("psycopg2")
psycopg2_module.OperationalError = OperationalError
psycopg2_module.InterfaceError = InterfaceError
psycopg2_module.connect = lambda *args, **kwargs: _FakeConn()
psycopg2_pool = types.ModuleType("psycopg2.pool")
psycopg2_pool.ThreadedConnectionPool = _FakePool
psycopg2_extras = types.ModuleType("psycopg2.extras")
psycopg2_extras.RealDictCursor = RealDictCursor
psycopg2_extras.execute_batch = execute_batch
psycopg2_module.pool = psycopg2_pool
psycopg2_module.extras = psycopg2_extras
sys.modules["psycopg2"] = psycopg2_module
sys.modules["psycopg2.pool"] = psycopg2_pool
sys.modules["psycopg2.extras"] = psycopg2_extras


# -------------------------------------------------------------------- httpx 桩
PROM_HTTP = {"status_code": 200, "payload": {"data": {"result": [{"value": [1700000000, "42"]}]}}, "raise": False}


class _SyncResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class SyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = sorted(kwargs.items())

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **kwargs):
        record("httpx.get", url=url, params=kwargs.get("params"), client_kwargs=self.kwargs)
        if PROM_HTTP["raise"]:
            raise RuntimeError("prometheus unreachable")
        return _SyncResponse(PROM_HTTP["status_code"], PROM_HTTP["payload"])


httpx_module = types.ModuleType("httpx")
httpx_module.Client = SyncClient
sys.modules["httpx"] = httpx_module


# ---------------------------------------------------------------- 固定 utcnow
class FakeDatetime(real_datetime.datetime):
    @classmethod
    def utcnow(cls):
        return FIXED_UTC


# ------------------------------------------------------------------ 日志捕获
class _CaptureHandler(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append({"level": record.levelname, "message": record.getMessage()})


capture = _CaptureHandler()
capture.setLevel(logging.DEBUG)
logging.getLogger("LogStorage").addHandler(capture)
logging.getLogger("LogStorage").setLevel(logging.DEBUG)


# -------------------------------------------------------------------- 导入被测
import api.app.services.log_storage as log_storage_module  # noqa: E402
from api.app.services.log_storage import log_storage  # noqa: E402

# 把 `from datetime import datetime` 绑定的名字换成假时钟（重构可能把导入挪到子模块）
for _name, _module in list(sys.modules.items()):
    if _name.startswith("api.app.services.log_storage") and hasattr(_module, "datetime"):
        _module.datetime = FakeDatetime

BOOTSTRAP_CALLS = list(CALLS)
CALLS.clear()

RESULTS = []


def scenario(name, fn):
    CALLS.clear()
    LOG_RECORDS.clear()
    buffer = io.StringIO()
    try:
        import contextlib

        with contextlib.redirect_stdout(buffer):
            value = fn()
        error = None
    except Exception as exc:
        value = None
        error = "%s: %s" % (type(exc).__name__, exc)
    RESULTS.append(
        {
            "case": name,
            "value": value,
            "error": error,
            "stdout": buffer.getvalue(),
            "calls": list(CALLS),
            "logs": list(LOG_RECORDS),
        }
    )


def set_plan(rows=None, rowcount=0):
    PLAN["rows"] = rows or []
    PLAN["rowcount"] = rowcount


def pool_mode(mode):
    log_storage.pool.mode = mode


def fail_execute(flag):
    log_storage.pool.fail_execute = flag


# --------------------------------------------------------------------- 场景
def main():
    RESULTS.append(
        {
            "case": "bootstrap",
            "value": None,
            "error": None,
            "stdout": "",
            "calls": BOOTSTRAP_CALLS,
            "logs": [],
        }
    )

    # 1. 配置读写
    set_plan(rows=[("sk-stored",)])
    scenario("config.get_found", lambda: log_storage.get_config("DEEPSEEK_API_KEY"))
    set_plan(rows=[])
    scenario("config.get_missing", lambda: log_storage.get_config("DEEPSEEK_MODEL"))
    set_plan(rows=[("x",)])
    scenario("config.set", lambda: log_storage.set_config("DEEPSEEK_MODEL", "deepseek-chat"))

    # 2. 事件写入：容器名与时间戳的多种形态
    set_plan(rowcount=1)
    scenario(
        "event.add_container_name",
        lambda: log_storage.add_event(
            {
                "rule": "falco_rule",
                "priority": "Warning",
                "source": "syscall",
                "hostname": "node-a",
                "time": "2024-04-30T10:00:00Z",
                "output_fields": {"container.name": "nginx", "evt.type": "openat"},
                "tags": ["a", "b"],
            }
        ),
    )
    scenario(
        "event.add_k8s_pod",
        lambda: log_storage.add_event(
            {
                "output_fields": {"k8s.pod.name": "api-0", "evt.time": 1700000000000},
            }
        ),
    )
    scenario(
        "event.add_hostname_fallback",
        lambda: log_storage.add_event({"hostname": "node-b", "output_fields": {"evt.time": 1700000000000}}),
    )
    scenario(
        "event.add_nanoseconds",
        lambda: log_storage.add_event({"output_fields": {"evt.time": 1700000000000000000}}),
    )
    scenario(
        "event.add_iso_iso8601",
        lambda: log_storage.add_event({"output_fields": {"container.id": "c-1", "evt.time.iso8601": "2024-04-30T10:00:00+00:00"}}),
    )
    scenario("event.add_no_time", lambda: log_storage.add_event({"output_fields": {}}))
    scenario("event.add_batch_empty", lambda: log_storage.add_event_batch([]))
    scenario(
        "event.add_batch_two",
        lambda: log_storage.add_event_batch(
            [
                {"output_fields": {"container.name": "a", "evt.time": 1700000000}},
                {"output_fields": {"container.name": "b", "evt.time": 1700000001}},
            ]
        ),
    )

    # 3. 日志查询
    set_plan(
        rows=[
            {
                "timestamp": 1700000000.0,
                "rule": "r1",
                "priority": "Warning",
                "source": "syscall",
                "output": {"evt.type": "openat"},
                "tags": ["x"],
            },
            {
                "timestamp": 1700000100.0,
                "rule": "r2",
                "priority": "Notice",
                "source": "syscall",
                "output": "已经序列化的字符串",
                "tags": '["json", "字符串"]',
            },
            {
                "timestamp": 1700000200.0,
                "rule": None,
                "priority": None,
                "source": None,
                "output": None,
                "tags": None,
            },
        ]
    )
    scenario("logs.by_container", lambda: log_storage.get_logs(container_id="nginx", limit=5, offset=2))
    scenario("logs.by_cursor_ts", lambda: log_storage.get_logs(container_id="nginx", limit=5, cursor_ts=1700000000.0))
    set_plan(rows=[])
    scenario("logs.empty", lambda: log_storage.get_logs(container_id="none"))

    # 4. 告警写入
    set_plan(rowcount=1)
    scenario(
        "alert.add",
        lambda: log_storage.add_alert(
            {"container.name": "nginx", "evt.type": "connect", "proc.name": "curl", "fd.name": "1.1.1.1:53->2.2.2.2:0", "evt.time": 1700000000},
            "network",
            "network attribute not matched",
            "2.2.2.2:0:ipv4",
        ),
    )
    scenario("alert.add_batch_empty", lambda: log_storage.add_alerts_batch([]))
    scenario(
        "alert.add_batch_two",
        lambda: log_storage.add_alerts_batch(
            [
                {"output_fields": {"container.name": "a", "evt.time": 1700000000}, "category": "process", "reason": "r", "attribute_value": "v"},
                {"output_fields": "不是字典", "category": None, "reason": None, "attribute_value": None},
            ]
        ),
    )

    # 5. 事件（incident）写入与更新
    scenario(
        "incident.add_full",
        lambda: log_storage.add_incident(
            container_id="nginx",
            timestamp=1700000000.0,
            threat_score=0.91,
            cluster_id=7,
            attribute_name="fd.name",
            attribute_value="1.1.1.1",
            event_type="connect",
            process_name="curl",
            alert_content="content",
            details="details",
            analysis_window=600,
            similarity_threshold=0.75,
            analysis="analysis text",
        ),
    )
    scenario(
        "incident.add_minimal",
        lambda: log_storage.add_incident(
            container_id="a",
            timestamp=1700000001,
            threat_score=0.1,
            cluster_id=None,
            attribute_name=None,
            attribute_value=None,
            event_type=None,
            process_name=None,
            alert_content=None,
            details=None,
        ),
    )
    set_plan(rowcount=1)
    scenario("incident.update_analysis", lambda: log_storage.update_incident_analysis(12, "新的分析"))

    # 6. 事件查询
    set_plan(
        rows=[
            {
                "id": 1,
                "container_id": "nginx",
                "timestamp": 1700000000.0,
                "threat_score": 0.9,
                "cluster_id": 3,
                "attribute_name": "fd.name",
                "attribute_value": "v",
                "event_type": "connect",
                "process_name": "curl",
                "alert_content": "c",
                "details": "d",
                "analysis_window": 300,
                "similarity_threshold": 0.8,
                "created_at": 1700000100.0,
                "analysis": None,
            }
        ]
    )
    scenario("incidents.no_filter", lambda: log_storage.get_incidents())
    scenario("incidents.container_only", lambda: log_storage.get_incidents(container_id="nginx", limit=10, offset=5))
    scenario("incidents.window_only", lambda: log_storage.get_incidents(window_seconds=1800, limit=10, offset=0))
    scenario("incidents.both", lambda: log_storage.get_incidents(container_id="nginx", window_seconds=60, limit=1, offset=0))
    scenario("incidents.window_zero", lambda: log_storage.get_incidents(window_seconds=0, limit=1, offset=0))
    set_plan(rows=[])
    scenario("incidents.empty", lambda: log_storage.get_incidents(container_id="none"))

    # 7. 告警统计
    set_plan(rows=[{"category": "process", "priority": "Warning", "cnt": "12"}, {"category": None, "priority": None, "cnt": 3}])
    scenario(
        "alert_stats.priority_window",
        lambda: log_storage.get_alert_stats("nginx", window_seconds=300, priority="Warning"),
    )
    scenario("alert_stats.priority_no_window", lambda: log_storage.get_alert_stats("nginx", window_seconds=0, priority="Warning"))
    scenario("alert_stats.window_only", lambda: log_storage.get_alert_stats("nginx", window_seconds=300))
    scenario("alert_stats.no_filter", lambda: log_storage.get_alert_stats("nginx", window_seconds=0))
    scenario("alert_stats.none_window", lambda: log_storage.get_alert_stats("nginx", window_seconds=None))
    set_plan(rows=[])
    scenario("alert_stats.empty", lambda: log_storage.get_alert_stats("nginx", window_seconds=300))

    # 8. 告警查询
    set_plan(
        rows=[
            {
                "container_id": "nginx",
                "timestamp": 1700000000.0,
                "category": "network",
                "reason": "reason",
                "evt_type": "connect",
                "proc_name": "curl",
                "fd_name": "1.1.1.1",
                "output": {"evt.type": "connect"},
                "attribute_value": "v",
            },
            {
                "container_id": "nginx",
                "timestamp": 1700000100.0,
                "category": None,
                "reason": None,
                "evt_type": None,
                "proc_name": None,
                "fd_name": None,
                "output": "已序列化",
                "attribute_value": None,
            },
        ]
    )
    scenario("alerts.by_container", lambda: log_storage.get_alerts(container_id="nginx", limit=3, offset=1))
    scenario("alerts.all_alias", lambda: log_storage.get_alerts(container_id="ALL", limit=3, offset=0))
    scenario("alerts.window", lambda: log_storage.get_alerts(container_id="nginx", window_seconds=600, limit=3))
    set_plan(rows=[])
    scenario("alerts.empty", lambda: log_storage.get_alerts(container_id="none"))

    # 9. 漏斗统计
    PROM_HTTP["status_code"] = 200
    PROM_HTTP["payload"] = {"data": {"result": [{"value": [1700000000, "42.9"]}]}}
    PROM_HTTP["raise"] = False
    set_plan(rows=[(5,)])
    scenario("funnel.windowed", lambda: log_storage.get_funnel_stats(window_seconds=1800))
    scenario("funnel.all_time", lambda: log_storage.get_funnel_stats(window_seconds=0))
    PROM_HTTP["status_code"] = 503
    scenario("funnel.prom_error_status", lambda: log_storage.get_funnel_stats(window_seconds=60))
    PROM_HTTP["raise"] = True
    scenario("funnel.prom_unreachable", lambda: log_storage.get_funnel_stats(window_seconds=60))
    PROM_HTTP["raise"] = False
    PROM_HTTP["status_code"] = 200
    PROM_HTTP["payload"] = {"data": {"result": []}}
    scenario("funnel.prom_empty_result", lambda: log_storage.get_funnel_stats(window_seconds=60))
    # 计数查询抛 OperationalError（表缺失等）时逐表跳过
    fail_execute(True)
    scenario("funnel.count_operational_error", lambda: log_storage.get_funnel_stats(window_seconds=60))
    fail_execute(False)

    # 10. 清理
    set_plan(rowcount=7)
    scenario("cleanup.events", lambda: log_storage.cleanup_old_data(retention_days=0.25))
    scenario("cleanup.alerts", lambda: log_storage.cleanup_old_alerts(retention_days=0.125))
    set_plan(rowcount=0)
    scenario("cleanup.nothing", lambda: log_storage.cleanup_old_data(retention_days=0.25))
    scenario("maintenance.vacuum", lambda: log_storage.vacuum_logs_db())

    # 11. 错误路径：执行期抛错
    fail_execute(True)
    set_plan(rowcount=0)
    scenario("error.get_config_execute", lambda: log_storage.get_config("K"))
    scenario("error.set_config_execute", lambda: log_storage.set_config("K", "V"))
    scenario("error.add_event_execute", lambda: log_storage.add_event({"output_fields": {"evt.time": 1700000000}}))
    scenario("error.get_logs_execute", lambda: log_storage.get_logs(container_id="nginx"))
    scenario("error.add_alert_execute", lambda: log_storage.add_alert({"evt.time": 1700000000}, "process", "r"))
    scenario("error.get_alerts_execute", lambda: log_storage.get_alerts(container_id="nginx"))
    scenario("error.get_incidents_execute", lambda: log_storage.get_incidents())
    scenario("error.get_alert_stats_execute", lambda: log_storage.get_alert_stats("nginx"))
    scenario("error.add_incident_execute", lambda: log_storage.add_incident(
        container_id="a", timestamp=1.0, threat_score=0.5, cluster_id=None, attribute_name=None,
        attribute_value=None, event_type=None, process_name=None, alert_content=None, details=None))
    scenario("error.add_event_batch_execute", lambda: log_storage.add_event_batch([{"output_fields": {}}]))
    scenario("error.add_alerts_batch_execute", lambda: log_storage.add_alerts_batch([{"output_fields": {}}]))
    scenario("error.update_incident_execute", lambda: log_storage.update_incident_analysis(1, "x"))
    scenario("error.cleanup_execute", lambda: log_storage.cleanup_old_data(retention_days=0.25))
    fail_execute(False)

    # 12. 错误路径：连接池取连接失败（重构中有意修正的两个方法）
    pool_mode("fail")
    set_plan(rowcount=0)
    scenario("pool.get_config_down", lambda: log_storage.get_config("K"))
    scenario("pool.set_config_down", lambda: log_storage.set_config("K", "V"))
    scenario("pool.get_logs_down", lambda: log_storage.get_logs(container_id="nginx"))
    scenario("pool.get_alerts_down", lambda: log_storage.get_alerts(container_id="nginx"))
    scenario("pool.get_incidents_down", lambda: log_storage.get_incidents())
    scenario("pool.add_event_down", lambda: log_storage.add_event({"output_fields": {}}))
    scenario("pool.cleanup_down", lambda: log_storage.cleanup_old_data(retention_days=0.25))
    scenario("pool.funnel_down", lambda: log_storage.get_funnel_stats(window_seconds=60))
    pool_mode("ok")

    payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


main()
