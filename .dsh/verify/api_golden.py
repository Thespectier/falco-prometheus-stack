"""API 层黄金输出验证。

用途：对 api/app 下的路由与入口做结构重构前后各运行一次，两次输出必须逐字节一致。
本机没有 fastapi / pydantic / 数据库，因此这里用桩件替换：

  * fastapi（APIRouter / HTTPException / Query / Body / WebSocket / FastAPI）
  * fastapi.middleware.cors、fastapi.responses
  * pydantic.BaseModel、pydantic_settings.BaseSettings
  * api.app.services.log_storage / prometheus / websocket_manager（记录调用并返回固定数据）
  * httpx（可切换远端行为的 AsyncClient 桩）

被验证的内容：

  * 每个路由模块注册的**路由表**（方法、路径、处理函数名、装饰器选项）
  * 每个处理函数在固定输入下的返回值、异常与 stdout
  * 对服务的调用序列与参数（证明没有漏调、重调或改变参数）
  * main 应用的 include_router 前缀/标签、中间件、healthz 与 verifyToken 的各分支

运行：python .dsh/verify/api_golden.py <输出文件>
"""

import asyncio
import contextlib
import importlib
import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, "tmp", "hbt")
os.makedirs(TMP, exist_ok=True)
sys.path.insert(0, ROOT)

os.environ["HBT_STORAGE_PATH"] = TMP
os.environ["ACCESS_CONTROL_ENABLED"] = "1"
os.environ.pop("PROMETHEUS_URL", None)
os.environ.pop("VERIFY_TOKEN_URL", None)

CALLS = []


def record(kind, **payload):
    CALLS.append({"call": kind, **payload})


# ---------------------------------------------------------------- fastapi 桩
class HTTPException(Exception):
    def __init__(self, status_code=None, detail=None, **kwargs):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class APIRouter:
    def __init__(self, *args, **kwargs):
        self.routes = []

    def _register(self, method, path, options):
        def decorator(func):
            self.routes.append(
                {"method": method, "path": path, "name": func.__name__, "options": sorted(options)}
            )
            return func

        return decorator

    def get(self, path, **options):
        return self._register("GET", path, options)

    def post(self, path, **options):
        return self._register("POST", path, options)

    def websocket(self, path, **options):
        return self._register("WEBSOCKET", path, options)


class WebSocket:
    pass


class WebSocketDisconnect(Exception):
    pass


def Query(default=None, **kwargs):
    return default


def Body(default=None, **kwargs):
    return default


class StreamingResponse:
    def __init__(self, content=None, media_type=None, **kwargs):
        self.content = content
        self.media_type = media_type


class FastAPI:
    def __init__(self, **kwargs):
        self.kwargs = {key: kwargs[key] for key in sorted(kwargs)}
        self.routes = []
        self.middleware = []

    def add_middleware(self, cls, **kwargs):
        self.middleware.append({"cls": cls.__name__, "kwargs": sorted(kwargs)})

    def include_router(self, router, **kwargs):
        self.routes.append({"prefix": kwargs.get("prefix"), "tags": kwargs.get("tags")})

    def get(self, path, **options):
        def decorator(func):
            self.routes.append({"method": "GET", "path": path, "name": func.__name__})
            return func

        return decorator


fastapi_module = types.ModuleType("fastapi")
fastapi_module.APIRouter = APIRouter
fastapi_module.HTTPException = HTTPException
fastapi_module.Query = Query
fastapi_module.Body = Body
fastapi_module.WebSocket = WebSocket
fastapi_module.WebSocketDisconnect = WebSocketDisconnect
fastapi_module.FastAPI = FastAPI
fastapi_module.Depends = lambda *args, **kwargs: None
sys.modules["fastapi"] = fastapi_module

cors_module = types.ModuleType("fastapi.middleware.cors")
cors_module.CORSMiddleware = type("CORSMiddleware", (), {})
sys.modules["fastapi.middleware"] = types.ModuleType("fastapi.middleware")
sys.modules["fastapi.middleware.cors"] = cors_module

responses_module = types.ModuleType("fastapi.responses")
responses_module.StreamingResponse = StreamingResponse
sys.modules["fastapi.responses"] = responses_module


# ------------------------------------------------------- pydantic / settings 桩
class BaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


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


pydantic_module = types.ModuleType("pydantic")
pydantic_module.BaseModel = BaseModel
sys.modules["pydantic"] = pydantic_module

pydantic_settings_module = types.ModuleType("pydantic_settings")
pydantic_settings_module.BaseSettings = BaseSettings
sys.modules["pydantic_settings"] = pydantic_settings_module


# ------------------------------------------------------------------- httpx 桩
class RequestError(Exception):
    def __init__(self, message, url="http://stub/api/v1/query"):
        super().__init__(message)
        self.request = type("_Request", (), {"url": url})()


class HTTPStatusError(Exception):
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.response = type("_Response", (), {"status_code": status_code})()


class _StubResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPStatusError("status %d" % self.status_code, self.status_code)


REMOTE = {"mode": "ok"}


class AsyncClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = sorted(kwargs.items())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, **kwargs):
        record("httpx.get", url=url, params=kwargs.get("params"))
        mode = REMOTE["mode"]
        if mode == "request_error":
            raise RequestError("connection refused")
        if mode == "status_error":
            raise HTTPStatusError("bad status", 503)
        if mode == "code_nonzero":
            return _StubResponse({"code": 7, "message": "token 已过期"})
        if mode == "no_message":
            return _StubResponse({"code": 7})
        return _StubResponse({"code": 0, "data": {"userId": "u-1", "userName": "tester"}})

    async def aclose(self):
        record("httpx.aclose")


httpx_module = types.ModuleType("httpx")
httpx_module.AsyncClient = AsyncClient
httpx_module.RequestError = RequestError
httpx_module.HTTPStatusError = HTTPStatusError
httpx_module.Client = type("Client", (), {})
sys.modules["httpx"] = httpx_module


# ------------------------------------------------------------ 服务层桩件
class _LogStorageStub:
    def get_funnel_stats(self, window_seconds=None):
        record("log_storage.get_funnel_stats", window_seconds=window_seconds)
        return {"logs": 3, "alerts": 2, "incidents": 1}

    def get_logs(self, container_id=None, limit=None, offset=None):
        record("log_storage.get_logs", container_id=container_id, limit=limit, offset=offset)
        return [{"id": 1, "container_id": container_id, "message": "sample"}]

    def get_alerts(self, container_id=None, window_seconds=None, limit=None, offset=None):
        record(
            "log_storage.get_alerts",
            container_id=container_id,
            window_seconds=window_seconds,
            limit=limit,
            offset=offset,
        )
        return [{"id": 9, "reason": "evt.type not matched"}]

    def get_incidents(self, container_id=None, window_seconds=None, limit=None, offset=None):
        record(
            "log_storage.get_incidents",
            container_id=container_id,
            window_seconds=window_seconds,
            limit=limit,
            offset=offset,
        )
        return [{"id": 5, "summary": "incident"}]

    def get_config(self, key):
        record("log_storage.get_config", key=key)
        return {"DEEPSEEK_API_KEY": "sk-test-key", "DEEPSEEK_MODEL": "deepseek-chat"}.get(key)

    def set_config(self, key, value):
        record("log_storage.set_config", key=key, value=value)


PROM = {"mode": "ok"}
PROM_RESPONSES = {
    "syscall_last_event_timestamp_seconds": {
        "status": "success",
        "data": {
            "result": [
                {"metric": {"container_name": "falco"}, "value": [1700000000, "1700000500"]},
                {"metric": {"container_name": "nginx"}, "value": [1700000000, "1700000600"]},
                {"metric": {}, "value": [1700000000, "1700000700"]},
            ]
        },
    },
    "sum by (container_name) (rate(syscall_events_total[5m]))": {
        "status": "success",
        "data": {
            "result": [
                {"metric": {"container_name": "falco"}, "value": [1700000000, "12.5"]},
                {"metric": {"container_name": "unknown"}, "value": [1700000000, "1.0"]},
                {"metric": {"container_name": "nginx"}, "value": [1700000000, "3"]},
            ]
        },
    },
    "sum(rate(syscall_events_total[5m]))": {
        "status": "success",
        "data": {"result": [{"metric": {}, "value": [1700000000, "18.25"]}]},
    },
    "sum by(priority) (rate(syscall_events_total[5m]))": {
        "status": "success",
        "data": {
            "result": [
                {"metric": {"priority": "Warning"}, "value": [1700000000, "4"]},
                {"metric": {}, "value": [1700000000, "2"]},
            ]
        },
    },
    "sum by(rule_category) (rate(syscall_events_total[5m]))": {
        "status": "success",
        "data": {
            "result": [
                {"metric": {"rule_category": "process"}, "value": [1700000000, "6.5"]},
                {"metric": {"rule_category": "network"}, "value": [1700000000, "not-a-number"]},
            ]
        },
    },
    "count(sum by(container_name) (rate(syscall_events_total[5m]) > 0))": {
        "status": "success",
        "data": {"result": [{"metric": {}, "value": [1700000000, "2"]}]},
    },
}


class _PrometheusStub:
    async def query(self, query, time_ts=None):
        record("prometheus.query", query=query, time_ts=time_ts)
        mode = PROM["mode"]
        if mode == "error":
            return {"status": "error", "errorType": "request_error"}
        if mode == "malformed":
            return {"status": "success", "data": {"result": [{"metric": {}, "value": ["bad"]}]}}
        return PROM_RESPONSES.get(query, {"status": "success", "data": {"result": []}})

    async def query_range(self, query, start, end, step=15):
        record("prometheus.query_range", query=query, start=start, end=end, step=step)
        return {"status": "success", "data": {"result": []}}


class _WebSocketManagerStub:
    async def connect(self, websocket, container_id):
        record("ws.connect", container_id=container_id)

    def disconnect(self, websocket, container_id):
        record("ws.disconnect", container_id=container_id)

    async def broadcast_batch(self, logs):
        record("ws.broadcast_batch", count=len(logs))


log_storage_module = types.ModuleType("api.app.services.log_storage")
log_storage_module.log_storage = _LogStorageStub()
sys.modules["api.app.services.log_storage"] = log_storage_module

prometheus_service_module = types.ModuleType("api.app.services.prometheus")
prometheus_service_module.prometheus_service = _PrometheusStub()
sys.modules["api.app.services.prometheus"] = prometheus_service_module

websocket_manager_module = types.ModuleType("api.app.services.websocket_manager")
websocket_manager_module.websocket_manager = _WebSocketManagerStub()
sys.modules["api.app.services.websocket_manager"] = websocket_manager_module


# ------------------------------------------------------------- 导入被测模块
import api.app.core.config as core_config  # noqa: E402
import api.app.main as main_module  # noqa: E402
from api.app.routers import (  # noqa: E402
    alerts,
    config as config_router,
    containers,
    hbt,
    incidents,
    incidents_container,
    logs,
    overview,
    stream,
)

SETTINGS = core_config.settings


class FakeWebSocket:
    """receive_text 在第 N 次调用后抛 WebSocketDisconnect，用来走完路由的 finally 分支。"""

    def __init__(self, disconnect_after=0):
        self.disconnect_after = disconnect_after
        self.calls = 0

    async def receive_text(self):
        self.calls += 1
        if self.calls > self.disconnect_after:
            raise WebSocketDisconnect()
        return "ping"


RESULTS = []


def jsonable(value):
    if isinstance(value, StreamingResponse):
        return {"streaming_media_type": value.media_type, "content_kind": type(value.content).__name__}
    if isinstance(value, BaseModel):
        return {"model": type(value).__name__, "fields": sorted(vars(value).items())}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def scenario(name, fn):
    """跑一个场景，记录返回值、异常、stdout 与期间发生的服务调用。"""
    CALLS.clear()
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            value = jsonable(asyncio.run(fn()))
        error = None
    except Exception as exc:
        value = None
        error = "%s: %s" % (type(exc).__name__, exc)
    RESULTS.append({"case": name, "value": value, "error": error, "stdout": buffer.getvalue(), "calls": list(CALLS)})


def sync_scenario(name, fn):
    scenario(name, lambda: _awaitable(fn()))


async def _awaitable(value):
    return value


# ------------------------------------------------------------------ 场景
def route_table(name, module):
    sync_scenario(name, lambda: list(module.router.routes))


def main():
    # 1. 路由表
    route_table("routes/containers", containers)
    route_table("routes/alerts", alerts)
    route_table("routes/overview", overview)
    route_table("routes/hbt", hbt)
    route_table("routes/stream", stream)
    route_table("routes/incidents", incidents)
    route_table("routes/incidents_container", incidents_container)
    route_table("routes/config", config_router)
    route_table("routes/logs", logs)

    sync_scenario(
        "app_surface",
        lambda: {
            "fastapi_kwargs": main_module.app.kwargs,
            "middleware": main_module.app.middleware,
            "included": main_module.app.routes,
            "app_prefix": main_module.APP_PREFIX,
            "access_control_enabled": main_module.ACCESS_CONTROL_ENABLED,
            "storage_path": SETTINGS.HBT_STORAGE_PATH,
            "project_name": SETTINGS.PROJECT_NAME,
            "api_v1_str": SETTINGS.API_V1_STR,
            "prometheus_url": SETTINGS.PROMETHEUS_URL,
        },
    )

    # 2. Prometheus 正常 / 报错 / 异常数据三种形态
    PROM["mode"] = "ok"
    scenario("containers.list_ok", lambda: containers.list_containers())
    scenario(
        "containers.logs",
        lambda: containers.get_container_logs(id="c1", start=1, end=2, limit=5, offset=3),
    )
    scenario("overview.ok", lambda: overview.get_overview())
    scenario(
        "alerts.list",
        lambda: alerts.get_container_alerts(id="c1", window_seconds=60, limit=10, offset=2),
    )
    scenario(
        "incidents.list",
        lambda: incidents.list_incidents(container_id="c1", window_seconds=0, limit=500, offset=0),
    )
    scenario(
        "incidents_container.list",
        lambda: incidents_container.get_container_incidents(id="c2", window_seconds=30, limit=7, offset=1),
    )

    PROM["mode"] = "error"
    scenario("containers.list_error", lambda: containers.list_containers())
    scenario("overview.error", lambda: overview.get_overview())

    PROM["mode"] = "malformed"
    scenario("overview.malformed", lambda: overview.get_overview())
    PROM["mode"] = "ok"

    # 3. HBT 快照：正常 / 缺失 / 内容损坏
    good = os.path.join(TMP, "container-good.json")
    with open(good, "w", encoding="utf-8") as handle:
        json.dump({"container_id": "container-good", "hbt_structure": {"name": "root"}}, handle)
    broken = os.path.join(TMP, "container-broken.json")
    with open(broken, "w", encoding="utf-8") as handle:
        handle.write("{not json at all")
    scenario("hbt.snapshot_ok", lambda: hbt.get_hbt_snapshot(id="container-good"))
    scenario("hbt.snapshot_missing", lambda: hbt.get_hbt_snapshot(id="container-missing"))
    scenario("hbt.snapshot_broken", lambda: hbt.get_hbt_snapshot(id="container-broken"))

    # 4. LLM 配置读写
    scenario("config.get_llm", lambda: config_router.get_llm_config())
    scenario(
        "config.set_llm_full",
        lambda: config_router.set_llm_config(
            config_router.LLMConfig(api_key="sk-new", endpoint="https://api.example.com", model="m1")
        ),
    )
    scenario(
        "config.set_llm_masked",
        lambda: config_router.set_llm_config(
            config_router.LLMConfig(api_key="********", endpoint="https://api.example.com", model="m2")
        ),
    )
    scenario(
        "config.set_llm_empty_key",
        lambda: config_router.set_llm_config(
            config_router.LLMConfig(api_key="", endpoint="https://api.example.com", model="m3")
        ),
    )

    # 5. 日志摄取与 WebSocket
    scenario("logs.ingest_batch", lambda: logs.ingest_logs(logs=[{"a": 1}, {"b": 2}]))
    scenario("logs.ingest_empty", lambda: logs.ingest_logs(logs=[]))
    scenario("logs.ws_disconnect", lambda: logs.websocket_endpoint(FakeWebSocket(0), "c9"))
    scenario("logs.ws_two_pings", lambda: logs.websocket_endpoint(FakeWebSocket(2), "c9"))

    # 6. SSE 流：只取第一帧（后面会 sleep 30s）
    async def first_chunk():
        generator = stream.event_generator("c7")
        return await generator.__anext__()

    scenario("stream.first_chunk", first_chunk)
    scenario("stream.endpoint", lambda: stream.stream_events(id="c7"))

    # 7. 入口：健康检查与 token 校验各分支
    scenario("main.healthz", lambda: main_module.health_check())
    scenario("main.verify_no_token", lambda: main_module.verify_token(token=None))
    scenario("main.verify_empty_token", lambda: main_module.verify_token(token=""))

    REMOTE["mode"] = "ok"
    scenario("main.verify_ok", lambda: main_module.verify_token(token="abc"))
    REMOTE["mode"] = "code_nonzero"
    scenario("main.verify_code_nonzero", lambda: main_module.verify_token(token="abc"))
    REMOTE["mode"] = "no_message"
    scenario("main.verify_no_message", lambda: main_module.verify_token(token="abc"))
    REMOTE["mode"] = "request_error"
    scenario("main.verify_request_error", lambda: main_module.verify_token(token="abc"))
    REMOTE["mode"] = "ok"

    # 8. 关闭访问控制后的分支（重新执行模块级代码）
    os.environ["ACCESS_CONTROL_ENABLED"] = "0"
    importlib.reload(main_module)
    scenario("main.verify_control_disabled", lambda: main_module.verify_token(token=None))
    os.environ["ACCESS_CONTROL_ENABLED"] = "1"
    importlib.reload(main_module)

    payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


main()
