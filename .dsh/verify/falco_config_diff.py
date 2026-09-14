"""对比 falco 的两份生效配置，找出本项目相对镜像默认值的全部覆盖项。

输入是 `falco --support` 的输出（每份文件的最后一行是 JSON）。只比对 `config` 字段，
逐层展开缺失/不同的键，输出一张扁平清单，用来生成最小配置。

运行：python .dsh/verify/falco_config_diff.py <当前配置的 support 输出> <默认配置的 support 输出>
"""

import json
import sys


def load_support(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith('{"cmdline"'):
                return json.loads(line)
    raise SystemExit("未在 %s 中找到 --support 的 JSON 输出" % path)


def flatten(node, prefix=""):
    """把嵌套配置摊平成 路径 -> 值。"""
    flat = {}
    if isinstance(node, dict):
        for key, value in node.items():
            flat.update(flatten(value, "%s.%s" % (prefix, key) if prefix else key))
    elif isinstance(node, list):
        if all(not isinstance(item, (dict, list)) for item in node):
            flat[prefix] = node
        else:
            for index, item in enumerate(node):
                flat.update(flatten(item, "%s[%d]" % (prefix, index)))
    else:
        flat[prefix] = node
    return flat


def main():
    current_path, default_path = sys.argv[1], sys.argv[2]
    current = json.loads(load_support(current_path)["config"])
    default = json.loads(load_support(default_path)["config"])

    flat_current = flatten(current)
    flat_default = flatten(default)

    changed = {}
    for key in sorted(flat_current):
        if key not in flat_default:
            changed[key] = ("新增", None, flat_current[key])
        elif flat_default[key] != flat_current[key]:
            changed[key] = ("改值", flat_default[key], flat_current[key])

    removed = [key for key in sorted(flat_default) if key not in flat_current]

    print("== 本项目相对镜像默认值的覆盖项（%d 项） ==" % len(changed))
    for key, (kind, old, new) in changed.items():
        if kind == "新增":
            print("  + %-60s = %r" % (key, new))
        else:
            print("  ~ %-60s %r -> %r" % (key, old, new))

    print()
    print("== 默认有、本项目未出现的键（%d 项） ==" % len(removed))
    for key in removed:
        print("  - %-60s (默认 %r)" % (key, flat_default[key]))


if __name__ == "__main__":
    main()
