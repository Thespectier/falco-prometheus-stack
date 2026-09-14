"""中小模块黄金输出验证：WebSocket 管理、Prometheus 客户端、分析服务、
日志/告警摄取器、Prometheus exporter、根目录回放脚本。

本机没有 fastapi / rich / prometheus_client / openai / httpx / docker，因此桩掉这些
依赖，并固定时钟。被验证的内容：

  * 每个公开函数/方法的返回值、异常、stdout 与日志记录
  * 记录到的外部调用（HTTP 请求、指标自增/赋值、LLM 请求体、队列操作）
  * WebSocket 广播的目标分组与报文内容
  * 摄取器的刷写条件（按批大小 / 按时间窗）

运行：python .dsh/verify/services_golden.py <输出文件>
"""

import asyncio
import contextlib
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

CLOCK = {"t": 1700000000.0}
SLEEP = {"calls": 0, "raise_on": None, "records": []}

import time as time_module  # noqa: E402

time_module.time = lambda: CLOCK["t"]

# 摄取器的日志里带刷写时刻，固定成常量以保证输出可比
time_module.strftime = lambda fmt, *args: "2024-05-01 12:00:00"


import threading  # noqa: E402

# 后台线程的长间隔睡眠用这个事件永久挂起，避免 fake_sleep 立刻返回导致热循环
PARK = threading.Event()


MAIN_THREAD = threading.main_thread()


def fake_sleep(seconds):
    if threading.current_thread() is not MAIN_THREAD:
        # 后台线程（摄取器的刷写循环）一律挂起：既避免热循环，也让记录只来自主线程
        PARK.wait()
        return
    SLEEP["calls"] += 1
    SLEEP["records"].append(seconds)
    if SLEEP["raise_on"] is not None and SLEEP["calls"] >= SLEEP["raise_on"]:
        raise KeyboardInterrupt()
    if seconds >= 60:
        PARK.wait()


time_module.sleep = fake_sleep

CALLS = []
LOG_RECORDS = []


def record(call, **payload):
    CALLS.append({"call": call, **payload})


class _CaptureHandler(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append({"logger": record.name, "level": record.levelname, "message": record.getMessage()})


logging.getLogger().addHandler(_CaptureHandler())
logging.getLogger().setLevel(logging.DEBUG)


# --------------------------------------------------------------------- fastapi 桩
class HTTPException(Exception):
    def __init__(self, status_code=None, detail=None, **kwargs):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class WebSocket:
    pass


class FastAPI:
    def __init__(self, **kwargs):
        self.kwargs = {key: kwargs[key] for key in sorted(kwargs)}
        self.routes = []

    def post(self, path, **options):
        def decorator(func):
            self.routes.append({"method": "POST", "path": path, "name": func.__name__})
            return func

        return decorator

    def get(self, path, **options):
        def decorator(func):
            self.routes.append({"method": "GET", "path": path, "name": func.__name__})
            return func

        return decorator


def Body(default=None, **kwargs):
    return default


fastapi_module = types.ModuleType("fastapi")
fastapi_module.FastAPI = FastAPI
fastapi_module.Body = Body
fastapi_module.WebSocket = WebSocket
fastapi_module.HTTPException = HTTPException
sys.modules["fastapi"] = fastapi_module


# ------------------------------------------------------------------------ rich 桩
class RichTree:
    def __init__(self, label, *args, **kwargs):
        self.label = label
        self.children = []

    def add(self, label, *args, **kwargs):
        node = RichTree(label)
        self.children.append(node)
        return node

    def dump(self):
        return {"label": self.label, "children": [child.dump() for child in self.children]}


rich_module = types.ModuleType("rich")
rich_module.print = lambda *args, **kwargs: record("rich.print", tree=args[0].dump() if hasattr(args[0], "dump") else repr(args[0]))
rich_tree_module = types.ModuleType("rich.tree")
rich_tree_module.Tree = RichTree
rich_module.tree = rich_tree_module
sys.modules["rich"] = rich_module
sys.modules["rich.tree"] = rich_tree_module


# ------------------------------------------------------------- prometheus_client 桩
class _MetricChild:
    def __init__(self, name, labels, kind):
        self.name = name
        self.labels = labels
        self.kind = kind

    def inc(self, amount=1):
        record("metric.inc", name=self.name, labels=self.labels, amount=amount)

    def set(self, value):
        record("metric.set", name=self.name, labels=self.labels, value=value)


class _Metric:
    def __init__(self, name, documentation, labelnames=None, kind="counter"):
        record("metric.created", name=name, documentation=documentation, labelnames=list(labelnames or []), kind=kind)
        self.name = name
        self.kind = kind

    def labels(self, **labels):
        return _MetricChild(self.name, {key: labels[key] for key in sorted(labels)}, self.kind)


prometheus_client_module = types.ModuleType("prometheus_client")
prometheus_client_module.Counter = lambda name, doc, labels=None: _Metric(name, doc, labels, "counter")
prometheus_client_module.Gauge = lambda name, doc, labels=None: _Metric(name, doc, labels, "gauge")
prometheus_client_module.start_http_server = lambda port: record("start_http_server", port=port)
sys.modules["prometheus_client"] = prometheus_client_module


# ----------------------------------------------------------------------- openai 桩
class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Completions:
    def __init__(self, plan):
        self.plan = plan

    def create(self, **kwargs):
        record(
            "openai.create",
            model=kwargs.get("model"),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            messages=kwargs.get("messages"),
        )
        if self.plan.get("raise"):
            raise RuntimeError("LLM 服务不可用")
        return type("_Response", (), {"choices": [_Choice(self.plan.get("content", "分析结果"))]})()


class OpenAI:
    def __init__(self, api_key=None, base_url=None, **kwargs):
        record("openai.client", api_key=api_key, base_url=base_url)
        self.chat = type("_Chat", (), {"completions": _Completions(OPENAI_PLAN)})()


OPENAI_PLAN = {"raise": False, "content": "分析结果"}

openai_module = types.ModuleType("openai")
openai_module.OpenAI = OpenAI
sys.modules["openai"] = openai_module


# ------------------------------------------------------------------------ httpx 桩
class RequestError(Exception):
    def __init__(self, message, url="http://stub/api/v1/query"):
        super().__init__(message)
        self.request = type("_Req", (), {"url": url})()


class HTTPStatusError(Exception):
    def __init__(self, message, status_code=500, url="http://stub/api/v1/query"):
        super().__init__(message)
        self.response = type("_Resp", (), {"status_code": status_code})()
        self.request = type("_Req", (), {"url": url})()


HTTP_PLAN = {"mode": "ok", "payload": {"status": "success", "data": {"result": []}}, "status_code": 200, "text": "ok"}


class _Response:
    def __init__(self, status_code, payload, text):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPStatusError("status %d" % self.status_code, self.status_code)


class _AsyncClient:
    def __init__(self, *args, **kwargs):
        record("httpx.async_client", args=list(args), kwargs=sorted(kwargs.items()))

    async def get(self, url, **kwargs):
        record("httpx.async_get", url=url, params=kwargs.get("params"))
        mode = HTTP_PLAN["mode"]
        if mode == "request_error":
            raise RequestError("connection refused")
        if mode == "status_error":
            raise HTTPStatusError("bad status", 503)
        if mode == "json_error":
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return _Response(HTTP_PLAN["status_code"], HTTP_PLAN["payload"], HTTP_PLAN["text"])

    async def aclose(self):
        record("httpx.async_close")


class _SyncClient:
    def __init__(self, *args, **kwargs):
        record("httpx.client", args=list(args), kwargs=sorted(kwargs.items()))

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, **kwargs):
        record("httpx.post", url=url, json=kwargs.get("json"))
        mode = HTTP_PLAN["mode"]
        if mode == "post_raise":
            raise RuntimeError("API 不可达")
        return _Response(HTTP_PLAN["status_code"], HTTP_PLAN["payload"], HTTP_PLAN["text"])


httpx_module = types.ModuleType("httpx")
httpx_module.AsyncClient = _AsyncClient
httpx_module.Client = _SyncClient
httpx_module.RequestError = RequestError
httpx_module.HTTPStatusError = HTTPStatusError
sys.modules["httpx"] = httpx_module


# ------------------------------------------------------------------ 队列与配置桩
class DockerLogQueue:
    def __init__(self, container_name=None, max_queue_size=None, **kwargs):
        record("queue.created", container_name=container_name, max_queue_size=max_queue_size)
        self.items = list(QUEUE_PLAN["items"])
        self.raise_after = QUEUE_PLAN["raise_after"]
        self.reads = 0

    def start(self):
        record("queue.start")

    def stop(self):
        record("queue.stop")

    def get(self, timeout=None):
        record("queue.get", timeout=timeout)
        self.reads += 1
        if QUEUE_PLAN["advance"]:
            CLOCK["t"] += QUEUE_PLAN["advance"]
        if self.raise_after is not None and self.reads >= self.raise_after:
            raise KeyboardInterrupt()
        if self.items:
            return self.items.pop(0)
        return None

    def get_stats(self):
        record("queue.get_stats")
        return {"received": self.reads, "dropped": 0}


QUEUE_PLAN = {"items": [], "raise_after": None, "advance": 0.0}

queue_module = types.ModuleType("hanabi.utils.queue")
queue_module.DockerLogQueue = DockerLogQueue
sys.modules["hanabi.utils.queue"] = queue_module


class _LogStorageStub:
    def get_config(self, key):
        record("log_storage.get_config", key=key)
        return STORAGE_PLAN.get(key)

    def get_incidents(self, **kwargs):
        record("log_storage.get_incidents", **kwargs)
        return list(STORAGE_PLAN.get("incidents", []))

    def update_incident_analysis(self, incident_id, analysis):
        record("log_storage.update_incident_analysis", incident_id=incident_id, analysis=analysis)

    def add_alerts_batch(self, batch):
        record("log_storage.add_alerts_batch", count=len(batch), items=list(batch))


STORAGE_PLAN = {"incidents": []}

log_storage_module = types.ModuleType("api.app.services.log_storage")
log_storage_module.log_storage = _LogStorageStub()
sys.modules["api.app.services.log_storage"] = log_storage_module


# ------------------------------------------------------- pydantic_settings 桩
class BaseSettings:
    def __init__(self, **overrides):
        for key, value in overrides.items():
            setattr(self, key, value)
        for key, value in vars(type(self)).items():
            if key.startswith("__") or isinstance(
                value, (types.FunctionType, classmethod, staticmethod, property, type)
            ):
                continue
            setattr(self, key, value)


pydantic_settings_module = types.ModuleType("pydantic_settings")
pydantic_settings_module.BaseSettings = BaseSettings
sys.modules["pydantic_settings"] = pydantic_settings_module


# -------------------------------------------------------------------- 导入被测模块
import api.app.services.websocket_manager as websocket_manager_module  # noqa: E402
import analyzer.service as analyzer_service  # noqa: E402
import ingestors.alerts.main as alerts_ingestor  # noqa: E402
import ingestors.logs.main as logs_ingestor  # noqa: E402
import main as replay_main  # noqa: E402
import prometheus.exporter as exporter  # noqa: E402
from api.app.services.prometheus import PrometheusService, prometheus_service  # noqa: E402
from api.app.services.websocket_manager import WebSocketManager, websocket_manager  # noqa: E402

# 摄取器的后台线程会让输出不确定：导入后立刻停掉模块级缓冲，后续用自建实例驱动
alerts_ingestor.alerts_buffer.stop()


# 固定 datetime.utcnow()，与假时钟保持一致（exporter 的时间戳兜底路径会用到）
class FakeDatetime(real_datetime.datetime):
    @classmethod
    def utcnow(cls):
        return real_datetime.datetime.fromtimestamp(
            CLOCK["t"], tz=real_datetime.timezone.utc
        ).replace(tzinfo=None)


for _module in (websocket_manager_module, exporter, analyzer_service, alerts_ingestor, logs_ingestor, replay_main):
    if hasattr(_module, "datetime"):
        _module.datetime = FakeDatetime

# 导入期发生的外部调用（指标声明、单例客户端的构造）也是契约，单独快照
IMPORT_CALLS = list(CALLS)
CALLS.clear()

RESULTS = []


def jsonable(value):
    if isinstance(value, RichTree):
        return value.dump()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, BaseException):
        return "%s: %s" % (type(value).__name__, value)
    return value


def scenario(name, fn):
    CALLS.clear()
    LOG_RECORDS.clear()
    SLEEP.update({"calls": 0, "records": [], "raise_on": None})
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            value = fn()
            if asyncio.iscoroutine(value):
                value = asyncio.run(value)
        error = None
    except BaseException as exc:  # KeyboardInterrupt 也是被验证的行为之一
        value = None
        error = "%s: %s" % (type(exc).__name__, exc)
    RESULTS.append(
        {
            "case": name,
            "value": jsonable(value),
            "error": error,
            "stdout": buffer.getvalue(),
            "calls": list(CALLS),
            "logs": list(LOG_RECORDS),
            "sleeps": list(SLEEP["records"]),
        }
    )


class FakeSocket:
    def __init__(self, fail=False):
        self.fail = fail
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, message):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(message)


def run():
    # ---------------------------------------------------------- WebSocket 管理
    scenario("ws.connect_disconnect", lambda: _ws_lifecycle())
    scenario("ws.broadcast", lambda: _ws_broadcast())
    scenario("ws.broadcast_skips_unknown", lambda: _ws_unknown())
    scenario("ws.send_failure_removes", lambda: _ws_failing())

    # ------------------------------------------------------- Prometheus 客户端
    HTTP_PLAN["mode"] = "ok"
    HTTP_PLAN["payload"] = {"status": "success", "data": {"result": [{"metric": {}, "value": [1, "2"]}]}}
    client = PrometheusService("http://prom:9090/")
    scenario("prom.query_ok", lambda: client.query("up", time_ts=1700000000.0))
    scenario("prom.query_no_ts", lambda: client.query("up"))
    HTTP_PLAN["mode"] = "request_error"
    scenario("prom.query_request_error", lambda: client.query("up"))
    HTTP_PLAN["mode"] = "status_error"
    scenario("prom.query_status_error", lambda: client.query("up"))
    HTTP_PLAN["mode"] = "json_error"
    scenario("prom.query_json_error", lambda: client.query("up"))
    HTTP_PLAN["mode"] = "ok"
    scenario("prom.query_range_ok", lambda: client.query_range("rate(x[5m])", 1.0, 2.0, step=30))
    HTTP_PLAN["mode"] = "request_error"
    scenario("prom.query_range_error", lambda: client.query_range("rate(x[5m])", 1.0, 2.0))
    HTTP_PLAN["mode"] = "ok"
    scenario("prom.close", lambda: client.close())
    scenario("prom.singleton_base_url", lambda: {"base_url": prometheus_service.base_url})

    # ------------------------------------------------------------------ 分析服务
    STORAGE_PLAN.clear()
    STORAGE_PLAN.update({"incidents": [], "DEEPSEEK_API_KEY": None, "DEEPSEEK_ENDPOINT": None, "DEEPSEEK_MODEL": None})
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("DEEPSEEK_ENDPOINT", None)
    os.environ.pop("DEEPSEEK_MODEL", None)
    scenario("analyzer.settings_defaults", lambda: analyzer_service.get_llm_settings())
    STORAGE_PLAN["DEEPSEEK_API_KEY"] = "sk-db"
    STORAGE_PLAN["DEEPSEEK_MODEL"] = "db-model"
    scenario("analyzer.settings_from_db", lambda: analyzer_service.get_llm_settings())
    STORAGE_PLAN["DEEPSEEK_API_KEY"] = None
    STORAGE_PLAN["DEEPSEEK_MODEL"] = None
    os.environ["DEEPSEEK_ENDPOINT"] = "https://env.example.com"
    scenario("analyzer.settings_env_endpoint", lambda: analyzer_service.get_llm_settings())
    os.environ.pop("DEEPSEEK_ENDPOINT", None)

    incident = {
        "id": 7,
        "process_name": "curl",
        "event_type": "connect",
        "threat_score": 0.87,
        "attribute_name": "fd.name",
        "attribute_value": "1.1.1.1:53",
        "details": "连接到可疑地址",
        "analysis": None,
    }
    OPENAI_PLAN.update({"raise": False, "content": "疑似数据外联"})
    scenario("analyzer.analyze_ok", lambda: analyzer_service.analyze_incident(OpenAI(api_key="k", base_url="u"), incident, "m1"))
    OPENAI_PLAN["raise"] = True
    scenario("analyzer.analyze_error", lambda: analyzer_service.analyze_incident(OpenAI(api_key="k", base_url="u"), incident, "m1"))
    OPENAI_PLAN["raise"] = False

    STORAGE_PLAN["incidents"] = [incident, dict(incident, id=8, analysis="已有结论")]
    STORAGE_PLAN["DEEPSEEK_API_KEY"] = "sk-db"
    scenario("analyzer.run_loop_one_round", lambda: _run_loop_until_sleep(2))
    STORAGE_PLAN["DEEPSEEK_API_KEY"] = None
    scenario("analyzer.run_loop_no_key", lambda: _run_loop_until_sleep(1))

    # ------------------------------------------------------------- 告警摄取器
    scenario("ingest_alerts.route_table", lambda: list(alerts_ingestor.app.routes))
    scenario("ingest_alerts.healthz", lambda: alerts_ingestor.healthz())
    buffer = alerts_ingestor.AlertsBuffer(batch_size=3, flush_interval=99)
    import atexit as atexit_module

    atexit_module.unregister(buffer.stop)
    scenario("ingest_alerts.buffer_add", lambda: _buffer_add(buffer))
    scenario("ingest_alerts.buffer_flush", lambda: buffer.flush())
    scenario("ingest_alerts.buffer_flush_empty", lambda: buffer.flush())
    small = alerts_ingestor.AlertsBuffer(batch_size=2, flush_interval=99)
    atexit_module.unregister(small.stop)
    scenario(
        "ingest_alerts.route_ingest",
        lambda: alerts_ingestor.ingest_alert({"category": "process", "reason": "r"}),
    )
    small.stop()
    scenario("ingest_alerts.singleton_state", lambda: {"buffer_len": len(alerts_ingestor.alerts_buffer.buffer), "running": alerts_ingestor.alerts_buffer.running})

    # ------------------------------------------------------------- 日志摄取器
    HTTP_PLAN["mode"] = "ok"
    HTTP_PLAN["status_code"] = 200
    scenario("ingest_logs.flush_empty", lambda: logs_ingestor.flush_buffer(_SyncClient(), []))
    scenario("ingest_logs.flush_ok", lambda: logs_ingestor.flush_buffer(_SyncClient(), [{"a": 1}]))
    HTTP_PLAN["status_code"] = 500
    HTTP_PLAN["text"] = "internal error"
    scenario("ingest_logs.flush_bad_status", lambda: logs_ingestor.flush_buffer(_SyncClient(), [{"a": 1}]))
    HTTP_PLAN["status_code"] = 200
    HTTP_PLAN["mode"] = "post_raise"
    scenario("ingest_logs.flush_exception", lambda: logs_ingestor.flush_buffer(_SyncClient(), [{"a": 1}]))
    HTTP_PLAN["mode"] = "ok"
    QUEUE_PLAN.update({"items": [{"evt": 1}, {"evt": 2}, {"evt": 3}], "raise_after": 4, "advance": 2.0})
    scenario("ingest_logs.run_flush_on_interval", lambda: logs_ingestor.run())
    QUEUE_PLAN.update({"items": [{"evt": 1}], "raise_after": 2, "advance": 0.0})
    scenario("ingest_logs.run_flush_on_kbd", lambda: logs_ingestor.run())

    # ------------------------------------------------------- prometheus exporter
    RESULTS.append(
        {
            "case": "import_time_calls",
            "value": None,
            "error": None,
            "stdout": "",
            "calls": IMPORT_CALLS,
            "logs": [],
            "sleeps": [],
        }
    )
    for rule, evt in [
        ("process", ""),
        ("PROC", ""),
        ("network", ""),
        ("net", ""),
        ("file", ""),
        ("other", "execve"),
        ("other", "clone"),
        ("other", "connect"),
        ("other", "listen"),
        ("other", "bind"),
        ("other", "openat"),
        ("other", "unlinkat"),
        ("other", "prctl"),
        ("", ""),
    ]:
        scenario("exporter.category_%s_%s" % (rule or "empty", evt or "empty"), lambda r=rule, e=evt: exporter._get_rule_category(r, e))
    scenario("exporter.ts_iso", lambda: exporter._parse_event_timestamp({"evt.time.iso8601": "2024-04-30T10:00:00Z"}))
    scenario("exporter.ts_iso_bad", lambda: exporter._parse_event_timestamp({"evt.time.iso8601": "不是时间"}))
    scenario("exporter.ts_ns", lambda: exporter._parse_event_timestamp({"evt.time": 1700000000000000000}))
    scenario("exporter.ts_ms", lambda: exporter._parse_event_timestamp({"evt.time": 1700000000000}))
    scenario("exporter.ts_sec", lambda: exporter._parse_event_timestamp({"evt.time": 1700000000}))
    scenario("exporter.ts_string", lambda: exporter._parse_event_timestamp({"evt.time": "1700000000"}))
    scenario("exporter.ts_missing", lambda: exporter._parse_event_timestamp({}))

    scenario(
        "exporter.process_event_ok",
        lambda: exporter.process_event(
            {
                "rule": "Terminal shell in container",
                "priority": "Notice",
                "output_fields": {
                    "container.name": "nginx",
                    "container.image.repository": "docker.io/library/nginx",
                    "proc.name": "bash",
                    "evt.type": "execve",
                    "k8s.ns.name": "default",
                    "evt.time.iso8601": "2024-04-30T10:00:00Z",
                },
            }
        ),
    )
    scenario(
        "exporter.process_event_no_container",
        lambda: exporter.process_event({"rule": "r", "output_fields": {"evt.type": "execve"}}),
    )
    scenario(
        "exporter.process_event_no_k8s",
        lambda: exporter.process_event(
            {"rule": "r", "output_fields": {"container.name": "c1", "evt.type": "connect", "evt.time": 1700000000}}
        ),
    )
    scenario("exporter.process_event_broken", lambda: exporter.process_event("不是字典"))
    QUEUE_PLAN.update({"items": [{"output_fields": {"container.name": "c1", "evt.type": "execve"}}], "raise_after": 2, "advance": 0.0})
    scenario("exporter.consume_events", lambda: exporter.consume_events(container_name="falco-test"))

    # -------------------------------------------------------- 根目录回放脚本
    QUEUE_PLAN.update({"items": [], "raise_after": None, "advance": 0.0})
    scenario("replay.get_model_statistics", lambda: replay_main.get_model_statistics(_StubModel()))
    QUEUE_PLAN.update(
        {
            "items": [
                {"evt.type": "execve", "proc.name": "bash"},
                {"evt.type": "connect", "proc.name": "curl", "fd.name": "1.1.1.1:53->2.2.2.2:40000"},
                {"evt.type": "openat", "proc.name": "bash", "fd.directory": "/etc", "fd.filename": "passwd"},
                {"evt.type": "prctl", "proc.name": "bash"},
            ],
            "raise_after": 6,
            "advance": 0.0,
        }
    )
    scenario("replay.main_flow", lambda: replay_main.main())

    payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


class _StubModel:
    def get_model(self):
        return {"container_id": "c", "hbt_structure": {"name": "root"}}


def _run_loop_until_sleep(raise_on):
    """在第 raise_on 次 sleep 时中断 run_loop（scenario 会先重置 sleep 计划）。"""
    SLEEP["raise_on"] = raise_on
    return analyzer_service.run_loop()


def _ws_lifecycle():
    manager = WebSocketManager()
    first = FakeSocket()
    second = FakeSocket()
    asyncio.run(manager.connect(first, "c1"))
    asyncio.run(manager.connect(second, "c1"))
    asyncio.run(manager.connect(FakeSocket(), "all"))
    manager.disconnect(first, "c1")
    manager.disconnect(second, "c1")
    manager.disconnect(FakeSocket(), "missing")
    return {"active_keys": sorted(manager.active_connections.keys()), "accepted": first.accepted}


def _ws_broadcast():
    manager = WebSocketManager()
    specific = FakeSocket()
    global_socket = FakeSocket()
    asyncio.run(manager.connect(specific, "nginx"))
    asyncio.run(manager.connect(global_socket, "all"))
    asyncio.run(
        manager.broadcast_batch(
            [
                {
                    "rule": "r1",
                    "priority": "Warning",
                    "source": "syscall",
                    "time": "2024-04-30T10:00:00Z",
                    "tags": ["标签", "b"],
                    "output_fields": {"container.name": "nginx", "evt.type": "openat", "描述": "中文"},
                },
                {
                    "output_fields": {"container.name": "nginx", "evt.time": 1700000000000},
                },
                {
                    "output_fields": {"container.name": "other"},
                    "time": 1700000000000000000,
                },
            ]
        )
    )
    return {"specific": specific.sent, "global": global_socket.sent}


def _ws_unknown():
    manager = WebSocketManager()
    global_socket = FakeSocket()
    asyncio.run(manager.connect(global_socket, "all"))
    asyncio.run(manager.broadcast_batch([{"output_fields": {}}, {"output_fields": {"container.name": ""}}]))
    return {"global": global_socket.sent, "keys": sorted(manager.active_connections.keys())}


def _ws_failing():
    manager = WebSocketManager()
    good = FakeSocket()
    bad = FakeSocket(fail=True)
    asyncio.run(manager.connect(good, "c1"))
    asyncio.run(manager.connect(bad, "c1"))
    asyncio.run(manager.broadcast_batch([{"output_fields": {"container.name": "c1"}}]))
    return {"remaining": len(manager.active_connections.get("c1", [])), "sent": good.sent}


def _buffer_add(buffer):
    buffer.add_alert({"category": "a"})
    buffer.add_alert({"category": "b"})
    return {"pending": len(buffer.buffer)}


run()
