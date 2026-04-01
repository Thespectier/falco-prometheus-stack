import os
from typing import Dict, Any, List
from .tree_node import TreeNode
from .branch_handlers import ProcessBranchHandler, NetworkBranchHandler, FileBranchHandler
from .event_parser import EventParser
from ..utils.timeCount import EventCounter


class HBTBuilder:
    """HBT模型构建器"""
    
    def __init__(self, container_id: str):
        """
        初始化HBT构建器
        
        Args:
            container_id: 容器ID
        """
        self.container_id = container_id
        self.root = TreeNode("root", "root")
        
        # 创建三个主分支
        self.process_branch = self.root.add_child("process_branch", "branch")
        self.network_branch = self.root.add_child("network_branch", "branch")
        self.file_branch = self.root.add_child("file_branch", "branch")
        
        # 初始化分支处理器
        warmup_seconds = int(os.environ.get("HANABI_WARMUP_SECONDS", 3600))
        self.eventCounter = EventCounter(warmup_seconds=warmup_seconds)
        self.process_handler = ProcessBranchHandler(self.process_branch)
        self.network_handler = NetworkBranchHandler(self.network_branch)
        self.file_handler = FileBranchHandler(self.file_branch)
        
        # 初始化事件解析器
        self.event_parser = EventParser()
    
    def add_event(self, event: Dict[str, Any]):
        """
        添加单个事件到HBT模型
        
        Args:
            event: 事件数据
        """
        # 提取输出字段
        output_fields = self.event_parser.extract_output_fields(event)
        
        # 对事件进行分类
        category = self.event_parser.categorize_event(event)
        
        # 根据分类将事件发送到相应的处理器
        if category == "process":
            self.process_handler.handle_event(output_fields,self.eventCounter)
        elif category == "network":
            self.network_handler.handle_event(output_fields,self.eventCounter)
        elif category == "file":
            self.file_handler.handle_event(output_fields,self.eventCounter)
        # 忽略未知类型的事件
    
    def add_events(self, events: List[Dict[str, Any]]):
        """
        批量添加事件到HBT模型
        
        Args:
            events: 事件数据列表
        """
        for event in events:
            self.add_event(event)
    
    def build_from_file(self, file_path: str):
        """
        从文件构建HBT模型
        
        Args:
            file_path: 事件文件路径
        """
        events = self.event_parser.parse_event_file(file_path)
        self.add_events(events)
    
    def get_model(self) -> Dict[str, Any]:
        """
        获取完整的HBT模型
        
        Returns:
            dict: HBT模型的字典表示
        """
        return {
            "container_id": self.container_id,
            "hbt_structure": self.root.to_dict()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取模型统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            "container_id": self.container_id,
            "total_events": (
                self.process_branch.events_count +
                self.network_branch.events_count +
                self.file_branch.events_count
            ),
            "process_events": self.process_branch.events_count,
            "network_events": self.network_branch.events_count,
            "file_events": self.file_branch.events_count
        }