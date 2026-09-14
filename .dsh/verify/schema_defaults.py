"""从 falco 的配置 schema 里读出各键的内置默认值。

schema 由 `falco --config-schema` 输出。若某个键带 "default"，说明不写该键时
Falco 就取这个值——这正是判断"哪些键可以从配置里删掉"的依据。

运行：python .dsh/verify/schema_defaults.py [键名前缀...]
"""

import json
import sys

SCHEMA_PATH = ".dsh/verify/config-schema.json"


def walk(node, path=""):
    """产出 (路径, 默认值) —— 只输出带 default 的叶子。"""
    if isinstance(node, dict):
        if "default" in node and not isinstance(node["default"], (dict,)):
            yield path, node["default"]
        for key, value in node.items():
            if key in ("properties", "definitions", "$defs"):
                for name, child in value.items():
                    yield from walk(child, "%s.%s" % (path, name) if path else name)
            elif key in ("items", "additionalProperties") and isinstance(value, dict):
                yield from walk(value, path + "[]")
    return


def main():
    prefixes = sys.argv[1:]
    with open(SCHEMA_PATH, encoding="utf-8") as handle:
        schema = json.load(handle)

    found = list(walk(schema))
    print("schema 中带 default 的键：%d 个" % len(found))
    for path, default in sorted(found):
        if not prefixes or any(path.lstrip(".").startswith(p) for p in prefixes):
            print("  %-58s = %r" % (path.lstrip("."), default))


if __name__ == "__main__":
    main()
