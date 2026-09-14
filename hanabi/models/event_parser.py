"""Falco 事件的读取、取字段与分支分类。

采集侧送进来的形态不固定：可能是 Falco 输出的整条 JSON，也可能是已经取好
output_fields 的字典；落盘的事件文件还可能是 JSONL、JSON 数组或单个对象。
本模块负责把这些形态统一成字典，并给每条事件打上 process / network / file
之一的分支标签——标签决定它落到行为树的哪棵子树。

分类先看 Falco 规则名（rule），规则名不可用时退回内核事件类型（evt.type）。
两张别名表分开维护，新增规则类型时只改表，不动判定逻辑。
"""

import json
from typing import Any, Dict, List, Union

# Falco 规则名 → 分支
_RULE_BRANCHES = {
    "process": "process",
    "proc": "process",
    "network": "network",
    "net": "network",
    "file": "file",
}

# 内核事件类型 → 分支
_EVENT_TYPE_BRANCHES = {
    "execve": "process",
    "clone": "process",
    "fork": "process",
    "vfork": "process",
    "connect": "network",
    "accept": "network",
    "send": "network",
    "recv": "network",
    "sendto": "network",
    "recvfrom": "network",
    "open": "file",
    "openat": "file",
    "close": "file",
    "read": "file",
    "write": "file",
    "unlink": "file",
    "unlinkat": "file",
}


def _events_from_lines(content: str) -> List[Dict[str, Any]]:
    """按行解析 JSONL；单行解析失败的直接跳过，不影响其它行。"""
    events: List[Dict[str, Any]] = []
    for line in content.split("\n"):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _events_from_document(content: str) -> List[Dict[str, Any]]:
    """把整份内容当作一个 JSON 值解析，并统一成列表。"""
    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        return []
    return document if isinstance(document, list) else [document]


class EventParser:
    """事件形态归一化与分支分类。"""

    @staticmethod
    def parse_event_data(data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """把单条事件归一化成字典；无法识别时给空字典而不是抛异常。"""
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def parse_event_file(file_path: str) -> List[Dict[str, Any]]:
        """读取事件文件，先按 JSONL 试，再退回整份 JSON。"""
        try:
            with open(file_path, "r") as handle:
                content = handle.read().strip()
        except FileNotFoundError:
            print(f"Warning: File {file_path} not found.")
            return []
        except Exception as error:
            print(f"Error parsing event file {file_path}: {str(error)}")
            return []

        events = _events_from_lines(content)
        if events:
            return events
        return _events_from_document(content)

    @staticmethod
    def extract_output_fields(event: Dict[str, Any]) -> Dict[str, Any]:
        """取出画像真正关心的字段集合。

        Falco 原始告警把字段放在 output_fields 下；回放/测试数据可能已经
        是字段集合本身，此时原样返回。
        """
        if "output_fields" in event:
            return event["output_fields"]
        return event

    @staticmethod
    def categorize_event(event: Dict[str, Any]) -> str:
        """判定事件归入哪条分支，无法判定时返回 unknown。

        这里对取值直接调用 lower()：非字符串的 rule / evt.type 属于上游数据
        异常，让它按原样抛错比静默归类更容易定位。
        """
        rule = event.get("rule", "").lower()
        branch = _RULE_BRANCHES.get(rule)
        if branch is not None:
            return branch

        evt_type = event.get("evt.type", "").lower()
        return _EVENT_TYPE_BRANCHES.get(evt_type, "unknown")
