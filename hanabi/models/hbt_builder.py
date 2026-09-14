"""把事件流装配成某个容器的 HBT 模型。

构建器持有一棵树、三个分支处理器和一个速率窗口。事件先取出 output_fields，
再按分类标签分派给对应分支；分类未知的事件（Falco 规则里大量与容器行为画像
无关的类型）直接丢弃，不入树也不报警。

三个分支的创建顺序就是序列化顺序，前端按这个顺序渲染子树。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from ..utils.timeCount import EventCounter
from .branch_handlers import FileBranchHandler, NetworkBranchHandler, ProcessBranchHandler
from .event_parser import EventParser
from .tree_node import TreeNode

_DEFAULT_WARMUP_SECONDS = 3600

# (分支节点名, 分类标签, 处理器)
_BRANCH_LAYOUT = (
    ("process_branch", "process", ProcessBranchHandler),
    ("network_branch", "network", NetworkBranchHandler),
    ("file_branch", "file", FileBranchHandler),
)


def _resolve_warmup_seconds() -> int:
    """学习期长度（秒）。默认一小时，用环境变量覆盖。"""
    return int(os.environ.get("HANABI_WARMUP_SECONDS", _DEFAULT_WARMUP_SECONDS))


class HBTBuilder:
    """单个容器的行为树构建器。"""

    def __init__(self, container_id: str):
        self.container_id = container_id
        self.root = TreeNode("root", "root")
        self.event_parser = EventParser()
        self.event_window = EventCounter(warmup_seconds=_resolve_warmup_seconds())
        self.branches: Dict[str, TreeNode] = {}
        self.handlers: Dict[str, Any] = {}
        for branch_name, category, handler_class in _BRANCH_LAYOUT:
            branch = self.root.add_child(branch_name, "branch")
            self.branches[category] = branch
            self.handlers[category] = handler_class(branch)

    def add_event(self, event: Dict[str, Any]) -> None:
        """并入一条事件；分类未知时忽略。"""
        output_fields = self.event_parser.extract_output_fields(event)
        handler = self.handlers.get(self.event_parser.categorize_event(event))
        if handler is not None:
            handler.handle_event(output_fields, self.event_window)

    def add_events(self, events: List[Dict[str, Any]]) -> None:
        """按顺序并入一批事件。"""
        for event in events:
            self.add_event(event)

    def build_from_file(self, file_path: str) -> None:
        """从事件文件（JSONL 或 JSON 数组）重建模型。"""
        self.add_events(self.event_parser.parse_event_file(file_path))

    def get_model(self) -> Dict[str, Any]:
        """导出模型：容器标识 + 整棵行为树。"""
        return {
            "container_id": self.container_id,
            "hbt_structure": self.root.to_dict(),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """按分支汇总命中次数。"""
        per_branch = {category: node.events_count for category, node in self.branches.items()}
        return {
            "container_id": self.container_id,
            "total_events": sum(per_branch.values()),
            "process_events": per_branch["process"],
            "network_events": per_branch["network"],
            "file_events": per_branch["file"],
        }
