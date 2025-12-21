from typing import Dict, Any
from .tree_node import TreeNode
import json
import re
import time
from ..utils.timeCount import EventCounter
from .embedding import has_semantic_match
import os
import json as _json
import httpx

learnState = True

def is_semantic_match(query: str, candidates_dict: dict) -> bool:
    """
    判断query是否与candidates_dict中的任一值语义匹配
    """
    if candidates_dict is None:
        return False
    candidates = list(candidates_dict.keys())
    return has_semantic_match(query, candidates)

def find_semantic_key(query: str, candidates_dict: dict) -> str:
    """
    在candidates_dict中查找与query语义匹配的key，如果没有匹配则返回query本身
    """
    return query
    # if candidates_dict is None or len(candidates_dict) == 0:
    #     return query
    
    # # 先尝试精确匹配
    # if query in candidates_dict:
    #     return query
    
    # # 再尝试语义匹配
    # for key in candidates_dict.keys():
    #     if has_semantic_match(query, [key]):
    #         return key
    
    # return query

def update_learn_state(eventCounter: EventCounter):
    """
    根据事件速率和时间窗口更新learnState
    在预热期间不进行判断，预热结束后才开始统计
    """
    global learnState
    
    # 如果还在预热期，直接返回，不进行判断
    if eventCounter.is_warmup_period():
        print("training (warmup period), eventCounter.get_rate():", eventCounter.get_rate())
        return
    
    now = int(time.time() * 1000)
    earliest_time = eventCounter.timestamps[0] if eventCounter.timestamps else now
    print("training, eventCounter.get_rate():", eventCounter.get_rate())
    print("time window:", now - earliest_time)
    if now - earliest_time >= 1000 * 120:
        eventCounter.clean_expired_events()  # 清理过期事件
        if eventCounter.get_rate() < 1:
            learnState = False
            print("Learning completed! Switching to detecting...")


def persist_alert(output_fields: dict, category: str, reason: str):
    url = os.getenv("ALERTS_INGESTOR_URL")
    if not url:
        return
    try:
        with httpx.Client(timeout=2.0) as c:
            c.post(f"{url}/alerts", json={
                "category": category,
                "reason": reason,
                "output_fields": output_fields,
                "ts": output_fields.get("evt.time") or output_fields.get("evt.time.iso8601")
            })
    except Exception:
        pass

class BranchHandler:
    """基础分支处理器"""
    
    def __init__(self, branch_root: TreeNode):
        """
        初始化分支处理器
        
        Args:
            branch_root: 分支根节点
        """
        self.root = branch_root
    
    def handle_event(self, event: Dict[str, Any],eventCounter: EventCounter):
        """
        处理事件的基础方法，需要在子类中实现
        
        Args:
            event: 事件数据
        """
        raise NotImplementedError("This method should be implemented by subclasses")

# using evt.type, proc.name to match the branch
class ProcessBranchHandler(BranchHandler):
    """进程分支处理器"""
    
    def handle_event(self, event: Dict[str, Any],eventCounter: EventCounter):
        """
        处理进程相关事件
        
        Args:
            event: 进程事件数据
        """
        if learnState == False:
            print("handle_event called with learnState=False")  # Debugging line
            evt_type = event.get("evt.type", "")
            proc_name = event.get("proc.name", "unknown")
            evt_key = find_semantic_key(evt_type, self.root.children)
            if evt_key not in self.root.children:
                print("warning(T):    " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "process", "evt.type not matched")
                return
            proc_key = find_semantic_key(proc_name, self.root.children[evt_key].children)
            if proc_key not in self.root.children[evt_key].children:
                print("Warning(T):    " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "process", "proc.name not matched")
                return
            # cmdline = event.get("proc.cmdline", "")
            # keys = re.findall(r'-{1,2}[^\s-]+', cmdline)
            # for k in keys:
            #     arg_key = find_semantic_key(k, self.root.children[evt_key].children[proc_key].children)
            #     if arg_key not in self.root.children[evt_key].children[proc_key].children:
            #         print("Warning(T):    " + json.dumps(event, ensure_ascii=False)+"\n")
            #         persist_alert(event, "process", "cmd argument not matched")
            #         break
            return
        # 获取进程相关信息
        # 获取operation layer级别的节点，即start、exit、prctl等
        evt_type = event.get("evt.type", "")
        evt_key = find_semantic_key(evt_type, self.root.children)
        if evt_key not in self.root.children:
            eventCounter.on_event()
            print("Warning(F):    " + json.dumps(event, ensure_ascii=False)+"\n")
            self.root.add_child(evt_type, "process_operation")
            evt_key = evt_type
        # 获取process layer级别的节点,即相应的proc.name
        proc_name = event.get("proc.name", "unknown")
        proc_key = find_semantic_key(proc_name, self.root.children[evt_key].children)
        if proc_key not in self.root.children[evt_key].children:
            eventCounter.on_event()
            print("Warning(F):    " + json.dumps(event, ensure_ascii=False)+"\n")
            self.root.children[evt_key].add_child(proc_name, "process_name")
            proc_key = proc_name
        # 获取Attribute Token Bag级别的节点，在进程中就是命令参数
        # cmdline = event.get("proc.cmdline", "")
        # keys = re.findall(r'-{1,2}[^\s-]+', cmdline)
        # for k in keys:
        #     arg_key = find_semantic_key(k, self.root.children[evt_key].children[proc_key].children)
        #     if arg_key not in self.root.children[evt_key].children[proc_key].children:
        #         eventCounter.on_event()
        #         print("Warning(F):    " + json.dumps(event, ensure_ascii=False)+"\n")
        #         self.root.children[evt_key].children[proc_key].add_child(k, "cmd_argument")
        #         arg_key = k
        #     self.root.children[evt_key].children[proc_key].children[arg_key].events_count += 1

        if learnState == True:
            update_learn_state(eventCounter)

# using evt.type, proc.name fd.type and fd.name to match the branch
class NetworkBranchHandler(BranchHandler):
    """网络分支处理器"""
    
    def handle_event(self, event: Dict[str, Any],eventCounter: EventCounter):
        """
        处理网络相关事件
        
        Args:
            event: 网络事件数据
        """
        if learnState == False:
            print("handle_event called with learnState=False")  # Debugging line
            evt_type = event.get("evt.type", "")
            proc_name = event.get("proc.name", "unknown")
            evt_key = find_semantic_key(evt_type, self.root.children)
            if evt_key not in self.root.children:
                print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "network", "evt.type not matched")
                return
            proc_key = find_semantic_key(proc_name, self.root.children[evt_key].children)
            if proc_key not in self.root.children[evt_key].children:
                print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "network", "proc.name not matched")
                return
            protocol = (event.get("fd.type") or "")
            str = event.get("fd.name", "")
            # 检查 fd.name 是否为 None 或空字符串
            if not str:
                return
            # 检查是否包含 "->" 分隔符
            if "->" not in str:
                right = ":"
            else:
                _ , right = str.split("->")
            value = right + ":" + (protocol or "")
            attr_key = find_semantic_key(value, self.root.children[evt_key].children[proc_key].children)
            if attr_key not in self.root.children[evt_key].children[proc_key].children:
                print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "network", "network attribute not matched")
            else:
                pass
            return
        # 获取网络相关信息
        # 获取operation layer级别的节点，即connection、listen、shutdown等
        evt_type = event.get("evt.type", "")
        evt_key = find_semantic_key(evt_type, self.root.children)
        if evt_key not in self.root.children:
            eventCounter.on_event()
            self.root.add_child(evt_type, "network_operation")
            evt_key = evt_type
        # 获取process layer级别的节点,即相应的proc.name
        proc_name = event.get("proc.name", "unknown")
        proc_key = find_semantic_key(proc_name, self.root.children[evt_key].children)
        if proc_key not in self.root.children[evt_key].children:
            eventCounter.on_event()
            self.root.children[evt_key].add_child(proc_name, "process_name")
            proc_key = proc_name
        # 获取Attribute Token Bag级别的节点，在网络中就是ip、port、protocol等
        protocol = (event.get("fd.type") or "")
        str = event.get("fd.name", "")
        # 检查 fd.name 是否为 None 或空字符串
        if not str:
            return
        if "->" not in str:
            right = ":"
        else:
            _ , right = str.split("->")
        value = right + ":" + (protocol or "")
        attr_key = find_semantic_key(value, self.root.children[evt_key].children[proc_key].children)
        if attr_key not in self.root.children[evt_key].children[proc_key].children:
            eventCounter.on_event()
            print("Warning(F): " + json.dumps(event, ensure_ascii=False)+"\n")
            self.root.children[evt_key].children[proc_key].add_child(value, "network_attribute")
            attr_key = value
        self.root.children[evt_key].children[proc_key].children[attr_key].events_count += 1

        if learnState == True:
            update_learn_state(eventCounter)

# using evt.type, proc.name and fd.directory to match the branch
class FileBranchHandler(BranchHandler):
    """文件分支处理器"""
    
    def handle_event(self, event: Dict[str, Any],eventCounter: EventCounter):
        """
        处理文件相关事件
        
        Args:
            event: 文件事件数据
        """
        if learnState == False:
            print("handle_event called with learnState=False")  # Debugging line
            evt_type = event.get("evt.type", "")
            proc_name = event.get("proc.name", "unknown")
            evt_key = find_semantic_key(evt_type, self.root.children)
            if evt_key not in self.root.children:
                print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "file", "evt.type not matched")
                return
            proc_key = find_semantic_key(proc_name, self.root.children[evt_key].children)
            if proc_key not in self.root.children[evt_key].children:
                print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
                persist_alert(event, "file", "proc.name not matched")
                return
            directory = event.get("fd.directory", "")
            # filename = event.get("fd.name", "")
            if directory:
                dir_key = find_semantic_key(directory, self.root.children[evt_key].children[proc_key].children)
                if dir_key not in self.root.children[evt_key].children[proc_key].children:
                    print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
                    persist_alert(event, "file", "directory not matched")
                    return
            # if filename:
            #     file_key = find_semantic_key(filename, self.root.children[evt_key].children[proc_key].children)
            #     if file_key not in self.root.children[evt_key].children[proc_key].children:
            #         print("Warning(T): " + json.dumps(event, ensure_ascii=False)+"\n")
            #         persist_alert(event, "file", "filename not matched")
            #         return
            # 匹配画像放行
            return
        # 获取文件相关信息
        # 获取operation layer级别的节点，即create、open、read、write、close等
        evt_type = event.get("evt.type", "")
        evt_key = find_semantic_key(evt_type, self.root.children)
        if evt_key not in self.root.children:
            eventCounter.on_event()
            self.root.add_child(evt_type, "file_operation")
            evt_key = evt_type
        # 获取process layer级别的节点,即相应的proc.name
        proc_name = event.get("proc.name", "unknown")
        proc_key = find_semantic_key(proc_name, self.root.children[evt_key].children)
        if proc_key not in self.root.children[evt_key].children:
            eventCounter.on_event()
            self.root.children[evt_key].add_child(proc_name, "process_name")
            proc_key = proc_name
        # 获取Attribute Token Bag级别的节点，在文件中就是directory和filename
        directory = event.get("fd.directory", "")
        # filename = event.get("fd.filename", "")
        if directory:
            dir_key = find_semantic_key(directory, self.root.children[evt_key].children[proc_key].children)
            if dir_key not in self.root.children[evt_key].children[proc_key].children:
                eventCounter.on_event()
                print("Warning(F): " + json.dumps(event, ensure_ascii=False)+"\n")
                self.root.children[evt_key].children[proc_key].add_child(directory, "directory_path")
                dir_key = directory
            self.root.children[evt_key].children[proc_key].children[dir_key].events_count += 1
        # if filename:
        #     file_key = find_semantic_key(filename, self.root.children[evt_key].children[proc_key].children)
        #     if file_key not in self.root.children[evt_key].children[proc_key].children:
        #         eventCounter.on_event()
        #         print("Warning(F): " + json.dumps(event, ensure_ascii=False)+"\n")
        #         self.root.children[evt_key].children[proc_key].add_child(filename, "file_name")
        #         file_key = filename
        #     self.root.children[evt_key].children[proc_key].children[file_key].events_count += 1

        if learnState == True:
            update_learn_state(eventCounter)
