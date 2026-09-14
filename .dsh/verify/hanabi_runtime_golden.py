"""hanabi 运行时黄金输出验证：DockerLogQueue（日志流队列）与 HanabiWorker。

本机没有 docker SDK，也没有可用的 Docker 容器，因此桩掉 `docker` 模块，并用脚本化的
日志分片驱动后台线程。被验证的内容：

  * `_stream_logs` 的分片拼行、JSON 解析、错误计数、停止事件与异常处理
  * `start()` 的三条失败分支与成功分支（含 stderr 输出）
  * 队列的 get/get_nowait/size/is_empty/get_stats
  * worker 的建模、事件分发、快照原子落盘、保存间隔、停止流程、信号处理

运行：python .dsh/verify/hanabi_runtime_golden.py <输出文件>
"""

import contextlib
import io
import json
import logging
import os
import shutil
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TMP_ROOT = os.path.join(HERE, "tmp")
WORKER_STORAGE = os.path.join(TMP_ROOT, "worker-storage")
sys.path.insert(0, ROOT)

os.environ["HBT_STORAGE_PATH"] = WORKER_STORAGE
os.environ["FALCO_CONTAINER"] = "test-falco"

CLOCK = {"t": 1700000000.0}
SLEEP_RECORDS = []

import time as time_module  # noqa: E402

time_module.time = lambda: CLOCK["t"]
time_module.sleep = lambda seconds: SLEEP_RECORDS.append(seconds)

CALLS = []
LOG_RECORDS = []


def record(call, **payload):
    CALLS.append({"call": call, **payload})


class _CaptureHandler(logging.Handler):
    def emit(self, record):
        LOG_RECORDS.append({"logger": record.name, "level": record.levelname, "message": record.getMessage()})


logging.getLogger().addHandler(_CaptureHandler())
logging.getLogger().setLevel(logging.DEBUG)


# --------------------------------------------------------------------- docker 桩
class DockerException(Exception):
    pass


class NotFound(DockerException):
    """真实 SDK 里 NotFound 是 DockerException 的子类，这里保持一致。"""


DOCKER_PLAN = {"mode": "ok", "short_id": "abc123def", "chunks": [], "raise_after": None}


class _Container:
    def __init__(self, name, plan):
        self.name = name
        self.short_id = plan["short_id"]
        self._plan = plan

    def logs(self, **kwargs):
        record("docker.logs", kwargs={key: kwargs[key] for key in sorted(kwargs)})
        for index, chunk in enumerate(self._plan["chunks"]):
            if self._plan["raise_after"] is not None and index >= self._plan["raise_after"]:
                raise RuntimeError("stream interrupted")
            yield chunk


class _Containers:
    def get(self, name):
        record("docker.containers.get", name=name)
        if DOCKER_PLAN["mode"] == "not_found":
            raise NotFound("no such container")
        if DOCKER_PLAN["mode"] == "docker_error":
            raise DockerException("cannot connect to daemon")
        return _Container(name, DOCKER_PLAN)


class _DockerClient:
    def __init__(self):
        self.containers = _Containers()


def _from_env():
    record("docker.from_env")
    return _DockerClient()


docker_module = types.ModuleType("docker")
docker_module.from_env = _from_env
docker_errors = types.ModuleType("docker.errors")
docker_errors.DockerException = DockerException
docker_errors.NotFound = NotFound
docker_module.errors = docker_errors
sys.modules["docker"] = docker_module
sys.modules["docker.errors"] = docker_errors


# ---------------------------------------------------------------- httpx 桩（branch_handlers 会 import）
class _StubHttpxClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, **kwargs):
        record("httpx.post", url=url)


httpx_module = types.ModuleType("httpx")
httpx_module.Client = _StubHttpxClient
sys.modules["httpx"] = httpx_module


from hanabi.utils.queue import DockerLogQueue  # noqa: E402
from hanabi.worker import HanabiWorker, signal_handler  # noqa: E402

# 把 queue 模块里的 datetime 换成假时钟：日志流的 since 参数必须可比
import datetime as _real_datetime  # noqa: E402


class _FakeDatetime(_real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return _real_datetime.datetime.fromtimestamp(
            CLOCK["t"], tz=_real_datetime.timezone.utc
        ).replace(tzinfo=None)


import hanabi.utils.queue as _queue_module  # noqa: E402

_queue_module.datetime = _FakeDatetime

RESULTS = []


def jsonable(value):
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
    SLEEP_RECORDS.clear()
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
            "sleeps": list(SLEEP_RECORDS),
        }
    )


def reset_storage():
    shutil.rmtree(WORKER_STORAGE, ignore_errors=True)
    os.makedirs(WORKER_STORAGE, exist_ok=True)


def snapshot_files():
    """读取落盘目录里的文件内容，用于比对原子写入的结果。"""
    files = {}
    for name in sorted(os.listdir(WORKER_STORAGE)):
        with open(os.path.join(WORKER_STORAGE, name), encoding="utf-8") as handle:
            files[name] = json.load(handle)
    return files


def run():
    reset_storage()

    # ---------------------------------------------------------- 队列基础行为
    def queue_basics():
        queue = DockerLogQueue(container_name="c1", max_queue_size=3)
        initial = [queue.is_empty(), queue.size(), queue.get_nowait(), queue.get(timeout=0.01)]
        queue.queue.put({"a": 1})
        queue.queue.put({"b": 2})
        filled = [queue.is_empty(), queue.size(), queue.get(), queue.get_nowait(), queue.get_nowait()]
        return {"initial": initial, "filled": filled, "stats": queue.get_stats()}

    scenario("queue.basics", queue_basics)

    # ------------------------------------------------------------- start 分支
    def start_ok():
        DOCKER_PLAN.update({"mode": "ok", "chunks": [b'{"evt": 1}\n{"evt": 2}\n'], "raise_after": None})
        queue = DockerLogQueue(container_name="c1", max_queue_size=10)
        queue.start()
        queue.thread.join(timeout=5)  # 先把有限的分片读完，保证统计确定
        drained = []
        while not queue.is_empty():
            drained.append(queue.get_nowait())
        stats_before_stop = queue.get_stats()
        queue.stop()
        return {"drained": drained, "stats_before_stop": stats_before_stop, "stats_after_stop": queue.get_stats()}

    def start_not_found():
        DOCKER_PLAN["mode"] = "not_found"
        queue = DockerLogQueue(container_name="missing")
        return queue.start()

    def start_docker_error():
        DOCKER_PLAN["mode"] = "docker_error"
        queue = DockerLogQueue(container_name="c1")
        return queue.start()

    scenario("queue.start_ok", start_ok)
    scenario("queue.start_not_found", start_not_found)
    scenario("queue.start_docker_error", start_docker_error)
    DOCKER_PLAN["mode"] = "ok"

    # ------------------------------------------------------- 日志分片解析
    def stream_lines():
        DOCKER_PLAN.update(
            {
                "chunks": [b'{"a": 1}\n{"b"', b': 2}\n', b"{bad json}\n", b"   \n", b'{"c": 3}\n'],
                "raise_after": None,
            }
        )
        queue = DockerLogQueue(container_name="c1", max_queue_size=10)
        queue.container = _Container("c1", DOCKER_PLAN)
        queue._stream_logs()
        drained = []
        while not queue.is_empty():
            drained.append(queue.get_nowait())
        return {"drained": drained, "stats": queue.get_stats()}

    def stream_stopped():
        DOCKER_PLAN.update({"chunks": [b'{"a": 1}\n'], "raise_after": None})
        queue = DockerLogQueue(container_name="c1")
        queue.container = _Container("c1", DOCKER_PLAN)
        queue.stop_event.set()
        queue._stream_logs()
        return {"stats": queue.get_stats()}

    def stream_interrupted():
        DOCKER_PLAN.update({"chunks": [b'{"a": 1}\n', b'{"b": 2}\n'], "raise_after": 1})
        queue = DockerLogQueue(container_name="c1", max_queue_size=10)
        queue.container = _Container("c1", DOCKER_PLAN)
        queue._stream_logs()
        return {"stats": queue.get_stats()}

    def stream_bad_encoding():
        DOCKER_PLAN.update({"chunks": [b"\xff\xfe not utf8\n"], "raise_after": None})
        queue = DockerLogQueue(container_name="c1")
        queue.container = _Container("c1", DOCKER_PLAN)
        queue._stream_logs()
        return {"stats": queue.get_stats()}

    def stream_interrupted_while_stopping():
        DOCKER_PLAN.update({"chunks": [b'{"a": 1}\n', b'{"b": 2}\n'], "raise_after": 1})
        queue = DockerLogQueue(container_name="c1")
        queue.container = _Container("c1", DOCKER_PLAN)
        queue.stop_event.set()
        queue._stream_logs()
        return {"stats": queue.get_stats()}

    scenario("queue.stream_lines", stream_lines)
    scenario("queue.stream_stopped", stream_stopped)
    scenario("queue.stream_interrupted", stream_interrupted)
    scenario("queue.stream_bad_encoding", stream_bad_encoding)
    scenario("queue.stream_interrupted_while_stopping", stream_interrupted_while_stopping)
    DOCKER_PLAN.update({"chunks": [], "raise_after": None})

    # --------------------------------------------------------------- worker
    PROCESS_EVENT = {"evt.type": "execve", "proc.name": "bash", "container.name": "web-1"}
    NETWORK_EVENT = {"evt.type": "connect", "proc.name": "curl", "container.name": "web-1", "fd.name": "1.1.1.1:53->2.2.2.2:40000"}
    FILE_EVENT = {"evt.type": "openat", "proc.name": "bash", "container.name": "web-2", "fd.directory": "/etc", "fd.filename": "passwd"}

    def worker_models():
        worker = HanabiWorker(container_name="c1", storage_path=WORKER_STORAGE)
        first = worker.get_or_create_model("web-1")
        second = worker.get_or_create_model("web-1")
        third = worker.get_or_create_model("web-2")
        return {"same_instance": first is second, "distinct": first is not third, "tracked": sorted(worker.models)}

    def worker_process_events():
        worker = HanabiWorker(container_name="c1", storage_path=WORKER_STORAGE)
        for event in (PROCESS_EVENT, NETWORK_EVENT, FILE_EVENT, {"evt.type": "prctl"}, {"output_fields": {}}, "不是字典"):
            worker.process_event(event)
        return {
            "containers": sorted(worker.models),
            "web1_children": sorted(worker.models["web-1"].get_model()["hbt_structure"]["children"]),
            "stats": worker.models["web-1"].hbt_builder.get_statistics(),
        }

    def worker_save_and_stop():
        worker = HanabiWorker(container_name="c1", storage_path=WORKER_STORAGE)
        worker.process_event(PROCESS_EVENT)
        worker.process_event(FILE_EVENT)
        worker.save_snapshots()
        files_after_save = snapshot_files()
        worker.stop()
        return {
            "files_after_save": sorted(files_after_save),
            "web1_container": files_after_save["web-1.json"]["container_id"],
            "files_after_stop": sorted(snapshot_files()),
            "running": worker.running,
        }

    def worker_start_loop():
        reset_storage()
        worker = HanabiWorker(container_name="c1", storage_path=WORKER_STORAGE)
        items = [PROCESS_EVENT, NETWORK_EVENT]
        reads = {"count": 0}

        def scripted_get(timeout=None):
            reads["count"] += 1
            record("worker.queue_get", timeout=timeout)
            if not items:
                raise KeyboardInterrupt()
            # 第二次读取时把时钟推过保存间隔，触发一次快照
            if reads["count"] == 2:
                CLOCK["t"] += 31
            return items.pop(0)

        worker.log_queue.get = scripted_get
        worker.start()
        return {"reads": reads["count"], "files": sorted(snapshot_files()), "running": worker.running}

    def worker_signal():
        return signal_handler(2, None)

    scenario("worker.models", worker_models)
    scenario("worker.process_events", worker_process_events)
    scenario("worker.save_and_stop", worker_save_and_stop)
    scenario("worker.start_loop", worker_start_loop)
    scenario("worker.signal_handler", worker_signal)

    payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


run()
