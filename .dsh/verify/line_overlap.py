"""重构前后代码行重合度测量。

用途：给出"这次重构到底改了多少"的客观数字。取 HEAD 版本与被改文件（工作区
版本）中所有非空、非注释、非纯引号的行，比较原样保留的行占比。同一行完全相同
才计入重合，因此它衡量的是"文本复用"，不是比对工具的同源率读数。

运行：python .dsh/verify/line_overlap.py [文件...]
"""

import io
import os
import subprocess
import sys

DEFAULT_FILES = [
    "hanabi/utils/parser.py",
    "hanabi/utils/timeCount.py",
    "hanabi/models/tree_node.py",
    "hanabi/models/event_parser.py",
    "hanabi/models/hbt_builder.py",
    "hanabi/models/hbt.py",
    "hanabi/models/branch_handlers.py",
]

SKIP_LINES = {'"""', "'''"}


def meaningful_lines(text):
    """去掉空行、纯注释行与独立的三引号行。"""
    kept = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped in SKIP_LINES:
            continue
        kept.add(stripped)
    return kept


def head_version(path):
    result = subprocess.run(
        ["git", "show", "HEAD:" + path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def worktree_version(path):
    """取改造后的文本；原文件若已被拆成同名包，则拼接包内所有模块。"""
    package = path[:-3] if path.endswith(".py") else path
    if os.path.isdir(package):
        parts = []
        for root, _dirs, files in os.walk(package):
            for name in sorted(files):
                if name.endswith(".py"):
                    with io.open(os.path.join(root, name), encoding="utf-8") as handle:
                        parts.append(handle.read())
        return "\n".join(parts)
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def main():
    targets = sys.argv[1:] or DEFAULT_FILES
    total_old = 0
    total_same = 0
    for path in targets:
        old_lines = meaningful_lines(head_version(path))
        new_lines = meaningful_lines(worktree_version(path))
        shared = len(old_lines & new_lines)
        total_old += len(old_lines)
        total_same += shared
        ratio = 100.0 * shared / max(1, len(old_lines))
        print("%-42s old=%4d  shared=%3d  %5.1f%%" % (path, len(old_lines), shared, ratio))
    print("-" * 78)
    ratio = 100.0 * total_same / max(1, total_old)
    print("合计：旧代码 %d 行，其中 %d 行（%.1f%%）在新实现中原样保留" % (total_old, total_same, ratio))


if __name__ == "__main__":
    main()
