"""HBT 模型层黄金输出验证脚本。

用途：对 hanabi 的模型层做结构重构前后各运行一次，两次输出必须逐字节一致。
它不修改被测代码，只通过公开 API 驱动，并且：

  * 固定时钟（time.time 被替换为假时钟），消除时间抖动
  * 捕获每个场景的 stdout（这些 print 属于被观察的行为）
  * 用桩替换 httpx，把 persist_alert 发出的请求记录下来
  * 学习期/检测期通过公开路径自然切换（warmup=0 + 推进时钟），不触碰模块内部变量

运行：python .dsh/verify/hbt_golden.py > <输出文件>
"""

import contextlib
import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TMP = os.path.join(HERE, "tmp")
os.makedirs(TMP, exist_ok=True)
sys.path.insert(0, ROOT)

# ---------------------------------------------------------------- 假时钟
CLOCK = {"ms": 1700000000000}

import time as _time_module

_time_module.time = lambda: CLOCK["ms"] / 1000.0


def advance(seconds):
    CLOCK["ms"] += int(seconds * 1000)


# ---------------------------------------------------------------- httpx 桩
POSTS = []


class _StubResponse:
    status_code = 200
    text = ""


class _StubClient:
    def __init__(self, *args, **kwargs):
        self.open_args = args
        self.open_kwargs = sorted(kwargs.items())

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def post(self, url, json=None):
        POSTS.append({"url": url, "body": json})
        return _StubResponse()


_stub_httpx = types.ModuleType("httpx")
_stub_httpx.Client = _StubClient
sys.modules["httpx"] = _stub_httpx

os.environ["ALERTS_INGESTOR_URL"] = "http://ingestor.test"
os.environ["HANABI_WARMUP_SECONDS"] = "0"

from hanabi.models.branch_handlers import BranchHandler  # noqa: E402
from hanabi.models.event_parser import EventParser  # noqa: E402
from hanabi.models.hbt import HBTModel  # noqa: E402
from hanabi.models.hbt_builder import HBTBuilder  # noqa: E402
from hanabi.models.tree_node import TreeNode  # noqa: E402
from hanabi.utils.parser import tokenize_attribute  # noqa: E402
from hanabi.utils.timeCount import EventCounter  # noqa: E402

RESULTS = []


def scenario(name, fn):
    """记录一个场景的返回值、stdout 与异常。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            value = fn()
            error = None
        except Exception as exc:  # 行为的一部分：异常类型与消息也要一致
            value = None
            error = f"{type(exc).__name__}: {exc}"
    RESULTS.append({"case": name, "stdout": buf.getvalue(), "value": value, "error": error})


# ------------------------------------------------- 0. 抽象基类的行为
def check_abstract_base():
    handler = BranchHandler(TreeNode("branch", "branch"))
    return handler.handle_event({"evt.type": "openat"}, EventCounter(warmup_seconds=0))


scenario("abstract_branch_handler", check_abstract_base)


# ------------------------------------------------------- 1. 属性泛化
TOKEN_INPUTS = [
    "123e4567-e89b-12d3-a456-426614174000",
    "src=10.20.30.40 dst=8.8.8.8",
    "d41d8cd98f00b204e9800998ecf8427e",
    "deadbeef",
    "123456789",
    "report-20240131.csv",
    "tmp.Whvbww",
    "/tmp/abc123def456ghi",
    "",
    None,
    0,
    98765,
    "<uuid>",
    "bash -c echo",
]


def check_tokenize():
    return [tokenize_attribute(item) for item in TOKEN_INPUTS]


scenario("tokenize_attribute", check_tokenize)


# ------------------------------------------------------- 2. 事件速率窗口
def check_counter_warmup():
    counter = EventCounter(warmup_seconds=3600)
    trace = [counter.is_warmup_period(), counter.get_rate()]
    for _ in range(3):
        counter.on_event()
    trace.append(counter.get_rate())
    trace.append(len(counter.timestamps))
    advance(3600)
    trace.append(counter.is_warmup_period())
    return trace


def check_counter_expiry():
    counter = EventCounter(warmup_seconds=0)
    for _ in range(4):
        counter.on_event()
        advance(20)
    before = [counter.get_rate(), len(counter.timestamps)]
    advance(61)
    counter.clean_expired_events()
    after = [counter.get_rate(), len(counter.timestamps)]
    counter.clean_expired_events()
    return [before, after, [counter.get_rate(), len(counter.timestamps)], counter.is_warmup_period()]


scenario("counter_warmup", check_counter_warmup)
scenario("counter_expiry", check_counter_expiry)


# ------------------------------------------------------- 3. 树节点
def check_tree_node():
    root = TreeNode("root", "root")
    proc = root.add_child("process_branch", "branch")
    again = root.add_child("process_branch", "branch")
    root.add_child("network_branch", "branch")
    proc.increment_events_count()
    proc.increment_events_count(4)
    proc.update_metadata("first_seen", "t0")
    proc.add_child("execve", "process_operation")
    leaf = proc.get_child("execve")
    leaf.increment_events_count(2)
    return {
        "same_instance": again is proc,
        "missing_child": root.get_child("nope"),
        "root": root.to_dict(),
        "fresh": TreeNode("空节点", "file").to_dict(),
    }


scenario("tree_node", check_tree_node)


# ------------------------------------------------------- 4. 事件解析
def check_parse_event_data():
    return [
        EventParser.parse_event_data('{"a": 1}'),
        EventParser.parse_event_data("{不是 json"),
        EventParser.parse_event_data({"b": 2}),
        EventParser.parse_event_data([1, 2]),
        EventParser.parse_event_data(None),
        EventParser.parse_event_data(7),
        EventParser.parse_event_data(""),
    ]


RULE_CASES = [
    {"rule": "process"},
    {"rule": "PROC"},
    {"rule": "proc"},
    {"rule": "network"},
    {"rule": "NET"},
    {"rule": "file"},
    {"rule": "File"},
    {"rule": "other"},
    {},
]
EVT_TYPE_CASES = [
    {"evt.type": "execve"},
    {"evt.type": "CLONE"},
    {"evt.type": "fork"},
    {"evt.type": "connect"},
    {"evt.type": "recvfrom"},
    {"evt.type": "openat"},
    {"evt.type": "WRITE"},
    {"evt.type": "unlinkat"},
    {"evt.type": "prctl"},
    {},
]


def check_categorize():
    by_rule = [(case, EventParser.categorize_event(case)) for case in RULE_CASES]
    by_type = [(case, EventParser.categorize_event(case)) for case in EVT_TYPE_CASES]
    return {"by_rule": by_rule, "by_evt_type": by_type}


def check_extract_fields():
    inner = {"evt.type": "openat"}
    return [
        EventParser.extract_output_fields({"output_fields": inner, "rule": "file"}),
        EventParser.extract_output_fields({"output_fields": {}}),
        EventParser.extract_output_fields(inner),
    ]


def check_parse_event_file():
    jsonl = os.path.join(TMP, "events.jsonl")
    with open(jsonl, "w", encoding="utf-8") as handle:
        handle.write('{"evt.type": "execve"}\n\n{"evt.type": "connect"}\n')

    array = os.path.join(TMP, "events-array.json")
    with open(array, "w", encoding="utf-8") as handle:
        handle.write('[{"evt.type": "openat"}, {"evt.type": "unlink"}]')

    single = os.path.join(TMP, "events-single.json")
    with open(single, "w", encoding="utf-8") as handle:
        handle.write('{"evt.type": "clone"}')

    broken = os.path.join(TMP, "events-broken.json")
    with open(broken, "w", encoding="utf-8") as handle:
        handle.write("这是一段无法解析的内容\n也不是 json\n")

    return [
        EventParser.parse_event_file(jsonl),
        EventParser.parse_event_file(array),
        EventParser.parse_event_file(single),
        EventParser.parse_event_file(broken),
        EventParser.parse_event_file(os.path.join(TMP, "no-such-file.json")),
    ]


scenario("parse_event_data", check_parse_event_data)
scenario("categorize_event", check_categorize)
scenario("extract_output_fields", check_extract_fields)
scenario("parse_event_file", check_parse_event_file)


# ------------------------------------------------------- 5. HBT 构建链路
PROCESS_EVENTS = [
    {"evt.type": "execve", "proc.name": "bash"},
    {"evt.type": "execve", "proc.name": "bash"},
    {"evt.type": "execve", "proc.name": "curl"},
    {"evt.type": "clone", "proc.name": "bash"},
]
NETWORK_EVENTS = [
    {"evt.type": "connect", "proc.name": "curl", "fd.type": "ipv4", "fd.name": "10.1.2.3:443->172.16.0.9:51514"},
    {"evt.type": "connect", "proc.name": "curl", "fd.type": "ipv4", "fd.name": "10.1.2.3:443->172.16.0.9:51515"},
    {"evt.type": "listen", "proc.name": "nginx", "fd.type": "ipv6"},
    {"evt.type": "connect", "proc.name": "curl", "fd.type": "ipv4", "fd.name": ""},
]
FILE_EVENTS = [
    {"evt.type": "openat", "proc.name": "bash", "fd.directory": "/etc", "fd.filename": "passwd"},
    {"evt.type": "openat", "proc.name": "bash", "fd.directory": "/etc", "fd.filename": "shadow"},
    {"evt.type": "write", "proc.name": "bash"},
]
UNKNOWN_EVENTS = [
    {"evt.type": "prctl", "proc.name": "bash"},
    {"proc.name": "bash"},
]

builder = HBTBuilder("container-abc")


def run_pipeline():
    builder.add_events(PROCESS_EVENTS)
    builder.add_events(NETWORK_EVENTS)
    builder.add_events(FILE_EVENTS)
    builder.add_events(UNKNOWN_EVENTS)
    builder.add_event({"rule": "process", "output_fields": {"evt.type": "execve", "proc.name": "ps"}})
    builder.add_event({"rule": "network", "output_fields": {"evt.type": "sendto"}})
    builder.add_event({"rule": "file", "output_fields": {"evt.type": "open", "fd.filename": "hosts"}})
    return {
        "statistics": builder.get_statistics(),
        "model": builder.get_model(),
    }


scenario("hbt_learning_phase", run_pipeline)

FACADE = HBTModel("container-facade")


def run_facade():
    FACADE.add_process_event({"evt.type": "execve", "proc.name": "sh"})
    FACADE.add_network_event({"evt.type": "connect", "proc.name": "sh", "fd.name": "1.1.1.1:53->2.2.2.2:40000"})
    FACADE.add_file_event({"evt.type": "unlink", "proc.name": "sh", "fd.directory": "/var", "fd.filename": "app.log"})
    return FACADE.get_model()


scenario("hbt_facade", run_facade)


# 推进时钟使速率窗口清空，下一次事件会把状态切到检测期（学习期结束）
def switch_to_detect():
    advance(130)
    builder.add_event({"evt.type": "execve", "proc.name": "bash"})


scenario("switch_to_detect", switch_to_detect)


def run_detect_matched():
    builder.add_event({"evt.type": "execve", "proc.name": "bash"})
    return builder.get_statistics()


def run_detect_process_mismatch():
    builder.add_event({"evt.type": "execve", "proc.name": "从未见过的进程"})
    return "returned"


def run_detect_new_evt_type():
    builder.add_event({"evt.type": "ptrace", "proc.name": "bash"})
    return "returned"


def run_detect_network():
    builder.add_event({"evt.type": "connect", "proc.name": "curl", "fd.type": "ipv4", "fd.name": "10.1.2.3:443->172.16.0.9:51516"})
    builder.add_event({"evt.type": "connect", "proc.name": "curl", "fd.type": "ipv4", "fd.name": "9.9.9.9:53->172.16.0.9:51517"})
    builder.add_event({"evt.type": "connect", "proc.name": "curl", "fd.type": "ipv4"})
    return "returned"


def run_detect_file():
    builder.add_event({"evt.type": "openat", "proc.name": "bash", "fd.directory": "/etc", "fd.filename": "hosts"})
    builder.add_event({"evt.type": "openat", "proc.name": "bash", "fd.directory": "/root", "fd.filename": "passwd"})
    builder.add_event({"evt.type": "openat", "proc.name": "bash", "fd.directory": "/etc", "fd.filename": "group"})
    return "returned"


scenario("detect_matched", run_detect_matched)
scenario("detect_process_mismatch", run_detect_process_mismatch)
scenario("detect_new_evt_type", run_detect_new_evt_type)
scenario("detect_network", run_detect_network)
scenario("detect_file", run_detect_file)


def check_final_model():
    return {"model": builder.get_model(), "statistics": builder.get_statistics()}


scenario("final_model", check_final_model)

RESULTS.append({"case": "posted_alerts", "stdout": "", "value": POSTS, "error": None})

payload = json.dumps(RESULTS, ensure_ascii=False, indent=2)
if len(sys.argv) > 1:
    with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload + "\n")
else:
    print(payload)
