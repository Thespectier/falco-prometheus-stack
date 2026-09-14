"""网络分支：以 evt.type（操作）、proc.name（进程）与对端地址为层。"""

import json
from typing import Any, Dict, Optional

from ...utils.timeCount import EventCounter
from .base import BranchHandler, generalize_key


class NetworkBranchHandler(BranchHandler):
    """网络行为画像。"""

    category = "network"
    operation_node_type = "network_operation"
    attribute_warning = "Warning(F): "

    def handle_event(self, event: Dict[str, Any], event_window: EventCounter):
        self._dispatch(event, event_window)

    @staticmethod
    def _peer_fingerprint(event: Dict[str, Any]) -> Optional[str]:
        """把 fd.name 折叠成"对端:协议"。

        fd.name 形如 "10.1.2.3:443->172.16.0.9:51514"：箭头左侧是本端，右侧
        才是画像关心的对端；没有箭头（listen 之类）时右侧用 ":" 占位。字段
        为空时返回 None，表示这一层不参与画像。
        """
        protocol = event.get("fd.type") or ""
        fd_name = event.get("fd.name", "")
        if not fd_name:
            return None
        if "->" not in fd_name:
            right = ":"
        else:
            _, right = fd_name.split("->")
        return right + ":" + protocol

    def _grow_attributes(
        self,
        event: Dict[str, Any],
        operation,
        process,
        event_window: EventCounter,
    ) -> bool:
        fingerprint = self._peer_fingerprint(event)
        if fingerprint is None:
            return False

        key = generalize_key(fingerprint)
        if key not in process.children:
            event_window.on_event()
            print(self.attribute_warning + json.dumps(event, ensure_ascii=False) + "\n")
            process.add_child(key, "network_attribute")
        process.children[key].events_count += 1
        return True

    def _verify_attributes(self, event: Dict[str, Any], operation, process) -> None:
        fingerprint = self._peer_fingerprint(event)
        if fingerprint is None:
            return
        if generalize_key(fingerprint) in process.children:
            return
        self._report(event, "network attribute not matched", fingerprint)
