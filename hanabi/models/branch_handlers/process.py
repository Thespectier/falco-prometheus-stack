"""进程分支：以 evt.type（操作）与 proc.name（进程）为层。

命令参数（proc.cmdline）那一层暂未启用：参数级画像在正常业务里噪声很大，
先只画像到进程粒度，等误报率数据出来再决定是否放开。
"""

from typing import Any, Dict

from ...utils.timeCount import EventCounter
from .base import BranchHandler


class ProcessBranchHandler(BranchHandler):
    """进程行为画像。"""

    category = "process"
    operation_node_type = "process_operation"
    level_warning = "Warning(F):    "
    detection_warning_by_reason = {
        # evt.type 未命中的文案历史上是小写 w，保留原样以免破坏既有日志检索
        "evt.type not matched": "warning(T):    ",
        "proc.name not matched": "Warning(T):    ",
    }

    def handle_event(self, event: Dict[str, Any], event_window: EventCounter):
        self._dispatch(event, event_window)

    def _grow_attributes(
        self,
        event: Dict[str, Any],
        operation,
        process,
        event_window: EventCounter,
    ) -> bool:
        """进程分支暂无属性层。"""
        return True

    def _verify_attributes(self, event: Dict[str, Any], operation, process) -> None:
        """进程分支暂无属性层。"""
        return
