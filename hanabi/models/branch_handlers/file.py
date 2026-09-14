"""文件分支：以 evt.type（操作）、proc.name（进程）与路径属性为层。

属性层有两条：目录（fd.directory）与文件名（fd.filename）。泛化之后
"/etc/passwd" 与 "/etc/shadow" 落在同一个目录节点、不同文件名节点上，
同一类行为在不同容器里就能对齐，而具体文件名仍然可区分。
"""

import json
from typing import Any, Dict, Tuple

from ...utils.timeCount import EventCounter
from .base import BranchHandler, generalize_key

# (事件字段, 节点类型, 检测期未命中原因)
_ATTRIBUTE_LAYERS: Tuple[Tuple[str, str, str], ...] = (
    ("fd.directory", "directory_path", "directory not matched"),
    ("fd.filename", "file_name", "filename not matched"),
)


class FileBranchHandler(BranchHandler):
    """文件行为画像。"""

    category = "file"
    operation_node_type = "file_operation"
    attribute_warning = "Warning(F): "

    def handle_event(self, event: Dict[str, Any], event_window: EventCounter):
        self._dispatch(event, event_window)

    def _grow_attributes(
        self,
        event: Dict[str, Any],
        operation,
        process,
        event_window: EventCounter,
    ) -> bool:
        for field, node_type, _reason in _ATTRIBUTE_LAYERS:
            value = event.get(field, "")
            if not value:
                continue

            key = generalize_key(value)
            if key not in process.children:
                event_window.on_event()
                print(self.attribute_warning + json.dumps(event, ensure_ascii=False) + "\n")
                process.add_child(key, node_type)
            process.children[key].events_count += 1
        return True

    def _verify_attributes(self, event: Dict[str, Any], operation, process) -> None:
        for field, _node_type, reason in _ATTRIBUTE_LAYERS:
            value = event.get(field, "")
            if not value:
                continue
            if generalize_key(value) in process.children:
                continue
            self._report(event, reason, value)
            return
