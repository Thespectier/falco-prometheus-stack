"""HBT 树的节点。

每个容器一棵树：根下面挂 process/network/file 三个分支，分支再按
"操作 → 进程 → 属性"逐层展开。节点自带命中计数与最近更新时间，写入端统一
通过 add_child 拿到（必要时创建）子节点，避免每个调用方各自判断存在性。

children 保持插入顺序：序列化结果直接给前端渲染，顺序变化会改变展示结构。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


class TreeNode:
    """行为树节点。"""

    __slots__ = ("name", "node_type", "children", "events_count", "metadata", "last_updated")

    def __init__(self, name: str, node_type: str):
        self.name = name
        self.node_type = node_type
        self.children: Dict[str, TreeNode] = {}
        self.events_count = 0
        self.metadata: Dict[str, Any] = {}
        self.last_updated = datetime.now()

    def add_child(self, child_name: str, child_type: str) -> TreeNode:
        """取回同名子节点，不存在则按给定类型建一个。"""
        child = self.children.get(child_name)
        if child is None:
            child = TreeNode(child_name, child_type)
            self.children[child_name] = child
        return child

    def get_child(self, child_name: str) -> Optional[TreeNode]:
        """按名字取子节点，未命中返回 None。"""
        return self.children.get(child_name)

    def increment_events_count(self, count: int = 1) -> None:
        """累加命中次数并刷新更新时间。"""
        self.events_count += count
        self.last_updated = datetime.now()

    def update_metadata(self, key: str, value: Any) -> None:
        """写入一条画像附注（首次出现时间、来源规则等）。"""
        self.metadata[key] = value
        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """递归导出为前端消费的字典结构。"""
        return {
            "name": self.name,
            "type": self.node_type,
            "events_count": self.events_count,
            "metadata": self.metadata,
            "children": {name: child.to_dict() for name, child in self.children.items()},
        }
