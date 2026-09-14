"""本地回放脚本：把 Falco 容器的日志流喂给 HBT 模型，退出时打印画像。

排障与演示用的入口，不参与容器编排——生产链路由 `hanabi/worker.py` 承担
（它同样消费容器日志，但会把模型落到共享存储并投递告警）。

运行：FALCO_CONTAINER=<容器名> python main.py
"""

import json

from rich import print as rprint
from rich.tree import Tree

from hanabi.models.event_parser import EventParser
from hanabi.models.hbt import HBTModel
from hanabi.models.tree_node import TreeNode
from hanabi.utils.queue import DockerLogQueue

# 分类标签 → HBTModel 上的方法名
_CATEGORY_HANDLERS = {
    "process": "add_process_event",
    "network": "add_network_event",
    "file": "add_file_event",
}


def _node_label(node: TreeNode, bold: bool) -> str:
    """节点的 Rich 标签；有事件数的节点带上计数。"""
    color = "bold blue" if bold else "blue"
    label = f"[{color}]{node.name}[/{color}] ({node.node_type})"
    if node.events_count > 0:
        label += f" [green]({node.events_count} events)[/green]"
    return label


def print_tree(node: TreeNode, tree: Tree = None, level: int = 0) -> Tree:
    """把 TreeNode 渲染成 Rich 树。

    首次调用（tree 为空）时创建根节点，之后每层挂到父节点上。level 参数保留
    只是为了兼容既有调用方式，渲染本身不需要它。
    """
    if tree is None:
        parent = Tree(_node_label(node, bold=True))
    else:
        parent = tree.add(_node_label(node, bold=False))

    for child in node.children.values():
        print_tree(child, parent, level + 1)

    return parent if tree is None else tree


def _rebuild_tree(node_dict, parent_node) -> None:
    """按序列化结果重建树，供 Rich 渲染（模型本体只在内存里，退出时已不可用）。"""
    for child_name, child_dict in node_dict["children"].items():
        child_node = parent_node.add_child(child_name, child_dict["type"])
        child_node.events_count = child_dict["events_count"]
        child_node.metadata = child_dict["metadata"]
        _rebuild_tree(child_dict, child_node)


def _report_final_model(hbt_model: HBTModel) -> None:
    """同时打印模型的 JSON 与树形两种形态。"""
    print("Final HBT model (JSON format):")
    print(json.dumps(hbt_model.get_model(), ensure_ascii=False, default=str))

    print("\nFinal HBT model (Tree format):")
    hbt_structure = hbt_model.get_model()["hbt_structure"]

    root_node = TreeNode(hbt_structure["name"], hbt_structure["type"])
    root_node.events_count = hbt_structure["events_count"]
    root_node.metadata = hbt_structure["metadata"]
    _rebuild_tree(hbt_structure, root_node)

    rprint(print_tree(root_node))


def main():
    """持续消费事件并维护模型；Ctrl+C 时打印画像。"""
    log_queue = DockerLogQueue(container_name="falco")
    log_queue.start()

    print("before HBTModel")
    hbt_model = HBTModel("falco_container")
    print("after HBTModel")
    print("before EventParser")
    event_parser = EventParser()
    print("after EventParser")

    try:
        count = 0
        while True:
            json_obj = log_queue.get(timeout=1)
            if not json_obj:
                continue

            count += 1
            print("log:", count)

            output_fields = event_parser.extract_output_fields(json_obj)
            category = event_parser.categorize_event(json_obj)
            handler = _CATEGORY_HANDLERS.get(category)
            if handler is None:
                # 未知分类（Falco 规则里与本项目无关的事件）直接跳过
                continue

            print(f"{category} log")
            getattr(hbt_model, handler)(output_fields)

    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
        _report_final_model(hbt_model)
    finally:
        log_queue.stop()


def get_model_statistics(hbt_model):
    """取模型的汇总信息；事件总数尚未接入统计口径，固定为 0。"""
    model = hbt_model.get_model()
    return {
        "container_id": model["container_id"],
        "total_events": 0
    }


if __name__ == "__main__":
    main()
