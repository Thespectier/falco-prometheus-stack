"""容器级 HBT 模型入口。

一个容器一个模型。采集侧（worker、回放脚本）只需要按类别把事件丢进来，不必
了解树的层次：三个 add_* 方法把事件包装成与分类标签同名的 Falco 规则名，再
交给构建器。
"""

from typing import Any, Dict

from .hbt_builder import HBTBuilder


class HBTModel:
    """某个容器的行为画像。"""

    def __init__(self, container_id: str):
        self.container_id = container_id
        self.hbt_builder = HBTBuilder(container_id)

    def add_process_event(self, event: Dict[str, Any]) -> None:
        """并入一条进程事件。"""
        self._feed("process", event)

    def add_network_event(self, event: Dict[str, Any]) -> None:
        """并入一条网络事件。"""
        self._feed("network", event)

    def add_file_event(self, event: Dict[str, Any]) -> None:
        """并入一条文件事件。"""
        self._feed("file", event)

    def get_model(self) -> Dict[str, Any]:
        """导出当前模型。"""
        return self.hbt_builder.get_model()

    def _feed(self, category: str, event: Dict[str, Any]) -> None:
        """按分支标签把事件交给构建器。"""
        self.hbt_builder.add_event({"rule": category, "output_fields": event})
