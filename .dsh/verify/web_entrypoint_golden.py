"""web/docker-entrypoint.sh 的行为黄金输出验证。

该脚本做的事只有两件：按 `ACCESS_CONTROL_ENABLED` 生成
`/usr/share/nginx/html/runtime-config.js`，然后把 CMD 交给 `exec`。所以验证方式就是
**在容器里真跑它**，把生成的文件内容与 exec 是否生效一并记录下来。

覆盖：变量未设置、`0` / `false` / `FALSE` / `False` / `no` / `NO` / `No`（脚本显式列举的
假值）、`1` / `true` / `yes`（真值）、以及一个未列举的取值（应落到默认分支 = 真）。

运行：python .dsh/verify/web_entrypoint_golden.py <输出文件>
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "web", "docker-entrypoint.sh")
TMP = os.path.join(ROOT, ".dsh", "verify", "tmp", "entrypoint.sh")


def prepared_script():
    """把脚本规范成 LF 再挂进容器。

    Windows 上 git 可能把工作区检出成 CRLF，而 busybox 的 `sh` 会把 `set -e\\r` 解析成
    非法选项（`illegal option -`）。交付物里是 LF，这里只做同一口径的预处理。
    """
    with open(SCRIPT, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    os.makedirs(os.path.dirname(TMP), exist_ok=True)
    with open(TMP, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text.replace("\r\n", "\n"))
    return TMP.replace("\\", "/")

# 脚本里显式列举的假值，加上真值与未列举值
CASES = [None, "0", "false", "FALSE", "False", "no", "NO", "No", "1", "true", "yes", "其他"]

# 容器里先建好目标目录，再跑脚本；`echo MARKER` 作为 CMD 用来确认 exec 生效
RUNNER = "mkdir -p /usr/share/nginx/html && sh /entry.sh echo MARKER && cat /usr/share/nginx/html/runtime-config.js"


def run_case(value):
    args = ["docker", "run", "--rm", "-v", "%s:/entry.sh:ro" % prepared_script()]
    if value is not None:
        args += ["-e", "ACCESS_CONTROL_ENABLED=%s" % value]
    args += ["alpine", "sh", "-c", RUNNER]

    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    body = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, [line for line in body.splitlines() if line.strip()]


def main():
    results = []
    for value in CASES:
        code, lines = run_case(value)
        results.append("ACCESS_CONTROL_ENABLED=%s -> exit=%d" % (value, code))
        results.extend("    %s" % line for line in lines)

    payload = "\n".join(results) + "\n"
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    else:
        sys.stdout.write(payload)
    print(payload)


if __name__ == "__main__":
    main()
