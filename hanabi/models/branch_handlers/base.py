"""三个分支处理器共用的骨架。

处理器有两种工作模式，由模块级的学习期开关决定：

* **学习期**：把没见过的层级补进树里，并把事件计入速率窗口；速率静下来之后
  学习期结束。
* **检测期**：只查询、不修改树。任何一层匹配不上就打印告警，并把事件投递给
  告警采集服务。

两种模式的层级定位顺序完全一致（操作 → 进程 → 属性），差别只在未命中时是补
节点还是报出去，因此骨架放在基类，各分支只声明自己的层次类型与文案。

告警文案与历史日志逐字一致（包括个别大小写与空格）：既有排查手册、日志检索和
告警规则都在按这些前缀匹配，改写它们等于改运维接口。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import httpx

from ..tree_node import TreeNode
from ...utils.parser import tokenize_attribute
from ...utils.timeCount import EventCounter

_MILLIS_PER_SECOND = 1000

# 安静多久算"已经越过启动抖动"
_QUIET_WINDOW_MILLIS = 120 * _MILLIS_PER_SECOND

# 告警投递超时：投递失败不能拖慢事件处理
_ALERT_TIMEOUT_SECONDS = 2.0

_DETECTION_ENTRY_LOG = "handle_event called with learnState=False"

_learning_phase_active = True


def generalize_key(value: Any) -> Any:
    """把事件里的具体取值折叠成占位符。

    树上存的就是泛化后的键，因此查询侧只需泛化待查的值即可直接命中，不必再做
    相似度匹配。
    """
    if not value:
        return value
    return tokenize_attribute(str(value))


def update_learn_state(event_window: EventCounter) -> None:
    """按事件速率判断学习期是否结束。

    预热期内不判定。预热结束后，如果事件窗口已经空了两分钟，说明容器越过了
    启动抖动阶段，切到检测期。
    """
    if event_window.is_warmup_period():
        print("training (warmup period), eventCounter.get_rate():", event_window.get_rate())
        return

    now = int(time.time() * _MILLIS_PER_SECOND)
    oldest = event_window.timestamps[0] if event_window.timestamps else now
    print("training, eventCounter.get_rate():", event_window.get_rate())
    print("time window:", now - oldest)

    if now - oldest < _QUIET_WINDOW_MILLIS:
        return

    event_window.clean_expired_events()
    if event_window.get_rate() >= 1:
        return

    print("Learning completed! Switching to detecting...")
    _leave_learning_phase()


def _leave_learning_phase() -> None:
    global _learning_phase_active
    _learning_phase_active = False


def publish_alert(output_fields: Dict[str, Any], category: str, reason: str, attribute_value: str = "") -> None:
    """把未命中画像的事件投递给告警采集服务；未配置地址时静默跳过。"""
    endpoint = os.getenv("ALERTS_INGESTOR_URL")
    if not endpoint:
        return

    try:
        with httpx.Client(timeout=_ALERT_TIMEOUT_SECONDS) as client:
            client.post(
                f"{endpoint}/alerts",
                json={
                    "category": category,
                    "reason": reason,
                    "output_fields": output_fields,
                    "ts": output_fields.get("evt.time") or output_fields.get("evt.time.iso8601"),
                    "attribute_value": attribute_value,
                },
            )
    except Exception:
        # 投递失败只影响告警可见性，不能中断事件处理
        pass


class BranchHandler:
    """分支处理器的公共骨架；子类声明层次类型与文案，并实现 handle_event。"""

    category = ""
    operation_node_type = ""
    # 学习期补"操作/进程"两层时的提示语；为空表示静默补
    level_warning = ""
    # 学习期补属性层时的提示语；为空表示静默补
    attribute_warning = ""
    # 检测期未命中的提示语，可按未命中原因细分
    detection_warning = "Warning(T): "
    detection_warning_by_reason: Dict[str, str] = {}

    def __init__(self, branch_root: TreeNode):
        self.root = branch_root

    def handle_event(self, event: Dict[str, Any], event_window: EventCounter):
        """子类实现；基类只声明层次约定。"""
        raise NotImplementedError("This method should be implemented by subclasses")

    # ---------------------------------------------------------- 内部骨架

    def _dispatch(self, event: Dict[str, Any], event_window: EventCounter) -> None:
        """三种分支共用的入口：检测期核对画像，学习期补树并更新速率状态。"""
        if not _learning_phase_active:
            self._verify(event)
            return
        if self._grow(event, event_window):
            update_learn_state(event_window)

    def _grow(self, event: Dict[str, Any], event_window: EventCounter) -> bool:
        """学习期：补齐"操作 → 进程"两层，再交给分支补属性层。

        返回值表示这次事件是否走完了属性层。网络分支在缺少对端字段时会提前
        结束，此时不更新速率状态——速率只统计真正进入画像的事件。
        """
        operation = self._grow_node(
            self.root,
            generalize_key(event.get("evt.type", "")),
            self.operation_node_type,
            event,
            event_window,
        )
        process = self._grow_node(
            operation,
            generalize_key(event.get("proc.name", "unknown")),
            "process_name",
            event,
            event_window,
        )
        return self._grow_attributes(event, operation, process, event_window)

    def _grow_node(
        self,
        parent: TreeNode,
        key: str,
        node_type: str,
        event: Dict[str, Any],
        event_window: EventCounter,
    ) -> TreeNode:
        """取回子节点；不存在时记一次事件、按需提示，然后建出来。"""
        existing = parent.children.get(key)
        if existing is not None:
            return existing

        event_window.on_event()
        if self.level_warning:
            print(self.level_warning + json.dumps(event, ensure_ascii=False) + "\n")
        return parent.add_child(key, node_type)

    def _grow_attributes(
        self,
        event: Dict[str, Any],
        operation: TreeNode,
        process: TreeNode,
        event_window: EventCounter,
    ) -> bool:
        """补属性层；返回 False 表示事件在此提前结束。"""
        raise NotImplementedError("This method should be implemented by subclasses")

    def _verify(self, event: Dict[str, Any]) -> None:
        """检测期：逐层核对，第一处未命中就报出去。"""
        print(_DETECTION_ENTRY_LOG)
        operation = self._require_node(
            self.root,
            generalize_key(event.get("evt.type", "")),
            event,
            "evt.type not matched",
            event.get("evt.type", ""),
        )
        if operation is None:
            return

        process = self._require_node(
            operation,
            generalize_key(event.get("proc.name", "unknown")),
            event,
            "proc.name not matched",
            event.get("proc.name", "unknown"),
        )
        if process is None:
            return

        self._verify_attributes(event, operation, process)

    def _require_node(
        self,
        parent: TreeNode,
        key: str,
        event: Dict[str, Any],
        reason: str,
        attribute_value: str,
    ) -> Optional[TreeNode]:
        """节点缺失时报警并返回 None，由调用方决定是否继续往下看。"""
        found = parent.children.get(key)
        if found is not None:
            return found
        self._report(event, reason, attribute_value)
        return None

    def _verify_attributes(self, event: Dict[str, Any], operation: TreeNode, process: TreeNode) -> None:
        raise NotImplementedError("This method should be implemented by subclasses")

    def _report(self, event: Dict[str, Any], reason: str, attribute_value: str = "") -> None:
        """打印并投递一条未命中告警。"""
        prefix = self.detection_warning_by_reason.get(reason, self.detection_warning)
        print(prefix + json.dumps(event, ensure_ascii=False) + "\n")
        publish_alert(event, self.category, reason, attribute_value)
