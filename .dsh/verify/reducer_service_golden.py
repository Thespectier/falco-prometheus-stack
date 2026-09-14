"""reducer/service.py 黄金输出验证。

需要用带依赖的解释器运行：`.dsh/verify/venv/Scripts/python.exe`。

桩掉 `httpx.Client`（Prometheus 查询）与 `api.app.services.log_storage`（存储层），
用真实 pandas 与真实 hanabi.reducer 跑消减流程；固定时钟、桩掉 tqdm。

被验证的内容：环境变量派生的常量（含按保留期算出的清理间隔）、容器发现的三条分支、
告警 → DataFrame 的字段映射与频次统计、单容器消减（空告警 / 有告警）、
一轮完整周期、主循环的清理与轮询分支。

运行：.dsh/verify/venv/Scripts/python.exe .dsh/verify/reducer_service_golden.py <输出文件>
"""

import contextlib
import importlib
import io
import json
import logging
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

os.environ.pop("PROMETHEUS_URL", None)
os.environ.pop("ALERTS_RETENTION_DAYS", None)
os.environ.pop("REDUCER_INTERVAL_SECONDS", None)

CLOCK = {"base": 1700000000.0, "step": 0.0, "calls": 0, "sleeps": [], "raise_on_sleep": None}


def fake_time():
    CLOCK["calls"] += 1
    return CLOCK["base"] + CLOCK["calls"] * CLOCK["step"]


def fake_sleep(seconds):
    CLOCK["sleeps"].append(seconds)
    if CLOCK["raise_on_sleep"] is not None and len(CLOCK["sleeps"]) >= CLOCK["raise_on_sleep"]:
        raise KeyboardInterrupt()


import time as time_module  # noqa: E402

time_module.time = fake_time
time_module.sleep = fake_sleep


class StubTqdm:
    def __init__(self, iterable=None, total=None, desc=None, unit=None, leave=None, **kwargs):
        self.iterable = iterable

    def __iter__(self):
        return iter(self.iterable) if self.iterable is not None else iter(())

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def update(self, n=1):
        return None

    def set_description(self, *args, **kwargs):
        return None

    @staticmethod
    def pandas(*args, **kwargs):
        import pandas as pd

        pd.DataFrame.progress_apply = pd.DataFrame.apply
        pd.Series.progress_apply = pd.Series.apply


tqdm_module = types.ModuleType("tqdm")
tqdm_module.tqdm = StubTqdm
sys.modules["tqdm"] = tqdm_module

CALLS = []
LOG_RECORDS = []


def record(call, **payload):
    CALLS.append({"call": call, **payload})


class _CaptureHandler(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append({"logger": record.name, "level": record.levelname, "message": record.getMessage()})


logging.getLogger().addHandler(_CaptureHandler())
logging.getLogger().setLevel(logging.DEBUG)


# ------------------------------------------------------------------- httpx 桩
PROM = {"mode": "ok", "containers": [{"metric": {"container_name": "nginx"}}, {"metric": {"container_name": "nginx"}}, {"metric": {"container_name": "api"}}, {"metric": {}}, {"metric": {"container_name": ""}}]}


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("status %d" % self.status_code)

    def json(self):
        return self._payload


class Client:
    def __init__(self, *args, **kwargs):
        self.kwargs = sorted(kwargs.items())

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, path, **kwargs):
        record("httpx.get", path=path, params=kwargs.get("params"), client_kwargs=self.kwargs)
        if PROM["mode"] == "raise":
            raise RuntimeError("prometheus unreachable")
        if PROM["mode"] == "http_error":
            return _Response(503, {})
        return _Response(200, {"data": {"result": PROM["containers"]}})


httpx_module = types.ModuleType("httpx")
httpx_module.Client = Client
sys.modules["httpx"] = httpx_module


# ------------------------------------------------------------- log_storage 桩
STORAGE = {"alerts": {}, "incidents": []}


class _LogStorageStub:
    def get_alerts(self, container_id=None, window_seconds=None, limit=None, offset=None):
        record("log_storage.get_alerts", container_id=container_id, window_seconds=window_seconds, limit=limit, offset=offset)
        return list(STORAGE["alerts"].get(container_id, []))

    def add_incident(self, **payload):
        record("log_storage.add_incident", **payload)
        STORAGE["incidents"].append(payload)

    def cleanup_old_alerts(self, retention_days=None):
        record("log_storage.cleanup_old_alerts", retention_days=retention_days)


log_storage_module = types.ModuleType("api.app.services.log_storage")
log_storage_module.log_storage = _LogStorageStub()
sys.modules["api.app.services.log_storage"] = log_storage_module


import reducer.service as service_module  # noqa: E402

RESULTS = []


def alert(index, **overrides):
    base = {
        "timestamp": 1700000000.0 + index,
        "category": "process",
        "reason": "evt.type not matched",
        "evt_type": "execve",
        "proc_name": "bash",
        "fd_name": "",
        "output": '{"evt.type": "execve"}',
        "attribute_value": "openat",
    }
    base.update(overrides)
    return base


def scripted_alerts():
    """覆盖：频次重复、属性值缺失回退、字段缺失、非字符串字段。"""
    return [
        alert(0),
        alert(1),
        alert(2, evt_type="connect", proc_name="curl", fd_name="1.1.1.1:53", attribute_value="", reason=""),
        alert(3, evt_type="connect", proc_name="curl", fd_name="1.1.1.1:53", attribute_value=""),
        alert(4, evt_type=None, proc_name=None, fd_name=None, attribute_value=None, reason=None, output=None),
        alert(5, evt_type="openat", proc_name="systemd", attribute_value="shadow"),
    ]


def jsonable(value):
    try:
        import pandas as pd
    except Exception:  # pragma: no cover
        pd = None
    if pd is not None and isinstance(value, pd.DataFrame):
        return {
            "columns": list(value.columns),
            "rows": json.loads(value.to_json(orient="records", force_ascii=False, date_format="iso")),
        }
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
    CLOCK.update({"calls": 0, "step": 0.0, "sleeps": [], "raise_on_sleep": None})
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            value = fn()
        error = None
    except BaseException as exc:
        value = None
        error = "%s: %s" % (type(exc).__name__, exc)
    RESULTS.append(
        {
            "case": name,
            "value": jsonable(value),
            "error": error,
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
            "calls": list(CALLS),
            "logs": list(LOG_RECORDS),
            "sleeps": list(CLOCK["sleeps"]),
        }
    )


def run():
    # ------------------------------------------------------------- 常量派生
    def constants():
        return {
            "prometheus_url": service_module.PROMETHEUS_URL,
            "poll": service_module.POLL_INTERVAL_SECONDS,
            "window": service_module.WINDOW_SECONDS,
            "similarity": service_module.SIMILARITY_THRESHOLD,
            "threat": service_module.THREAT_THRESHOLD,
            "max_per_cluster": service_module.MAX_PER_CLUSTER,
            "retention_days": service_module.RETENTION_DAYS,
            "cleanup_interval": service_module.CLEANUP_INTERVAL,
            "vacuum_interval": service_module.VACUUM_INTERVAL,
            "alerts_retention_days": service_module.ALERTS_RETENTION_DAYS,
            "alerts_cleanup_interval": service_module.ALERTS_CLEANUP_INTERVAL,
        }

    scenario("service.constants_defaults", constants)

    def constants_custom():
        os.environ["ALERTS_RETENTION_DAYS"] = "2.0"
        os.environ["REDUCER_INTERVAL_SECONDS"] = "90"
        os.environ["PROMETHEUS_URL"] = "http://prom.local:9090/"
        try:
            importlib.reload(service_module)
            return {
                "alerts_retention_days": service_module.ALERTS_RETENTION_DAYS,
                "alerts_cleanup_interval": service_module.ALERTS_CLEANUP_INTERVAL,
                "poll": service_module.POLL_INTERVAL_SECONDS,
                "prometheus_url": service_module.PROMETHEUS_URL,
            }
        finally:
            for key in ("ALERTS_RETENTION_DAYS", "REDUCER_INTERVAL_SECONDS", "PROMETHEUS_URL"):
                os.environ.pop(key, None)
            importlib.reload(service_module)

    scenario("service.constants_custom", constants_custom)

    # --------------------------------------------------------- 容器发现分支
    def list_ok():
        return service_module._list_containers(Client(base_url="http://prom", timeout=5.0))

    def list_http_error():
        PROM["mode"] = "http_error"
        try:
            return service_module._list_containers(Client())
        finally:
            PROM["mode"] = "ok"

    def list_raise():
        PROM["mode"] = "raise"
        try:
            return service_module._list_containers(Client())
        finally:
            PROM["mode"] = "ok"

    scenario("service.list_containers_ok", list_ok)
    scenario("service.list_containers_http_error", list_http_error)
    scenario("service.list_containers_raises", list_raise)

    # ------------------------------------------------------------ 字段映射
    def to_frame():
        service_module._alerts_to_dataframe.__globals__
        return service_module._alerts_to_dataframe(scripted_alerts())

    def to_frame_empty():
        return service_module._alerts_to_dataframe([])

    scenario("service.alerts_to_dataframe", to_frame)
    scenario("service.alerts_to_dataframe_empty", to_frame_empty)

    # -------------------------------------------------------------- 消减
    def reduce_empty():
        return service_module._reduce_for_container("nginx", [])

    def reduce_with_alerts():
        return service_module._reduce_for_container("nginx", scripted_alerts())

    scenario("service.reduce_empty", reduce_empty)
    scenario("service.reduce_with_alerts", reduce_with_alerts)

    # ---------------------------------------------------------- 一轮完整周期
    def run_once():
        STORAGE["alerts"] = {"nginx": scripted_alerts(), "api": []}
        STORAGE["incidents"] = []
        service_module.run_once()
        return {
            "incidents": len(STORAGE["incidents"]),
            "incident_container": STORAGE["incidents"][0]["container_id"] if STORAGE["incidents"] else None,
        }

    scenario("service.run_once", run_once)

    def run_once_no_containers():
        PROM["containers"] = []
        STORAGE["incidents"] = []
        try:
            return service_module.run_once()
        finally:
            PROM["containers"] = [{"metric": {"container_name": "nginx"}}, {"metric": {"container_name": "nginx"}}, {"metric": {"container_name": "api"}}, {"metric": {}}, {"metric": {"container_name": ""}}]
            PROM["mode"] = "ok"

    scenario("service.run_once_no_containers", run_once_no_containers)

    # -------------------------------------------------------------- 主循环
    def main_first_cycle():
        STORAGE["alerts"] = {"nginx": scripted_alerts(), "api": []}
        STORAGE["incidents"] = []
        CLOCK["raise_on_sleep"] = 2  # 第一次 sleep(60) 放行，轮询 sleep 时退出
        return service_module.main()

    def main_cleanup_skipped():
        STORAGE["alerts"] = {}
        STORAGE["incidents"] = []
        CLOCK["step"] = 1.0
        CLOCK["raise_on_sleep"] = 2
        # 让第一次判断的 now 已远大于清理间隔，随后时钟推进很少 → 第二次不再触发清理
        CLOCK["base"] = 1000.0
        try:
            return service_module.main()
        finally:
            CLOCK["base"] = 1700000000.0

    scenario("service.main_first_cycle", main_first_cycle)
    scenario("service.main_early_no_cleanup", main_cleanup_skipped)

    payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


run()
