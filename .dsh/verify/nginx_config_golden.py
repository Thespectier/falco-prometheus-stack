"""nginx 配置的指令级黄金输出验证。

比对方式：把配置挂进 `nginx:alpine`，用 `nginx -T` 转储生效配置，然后**去掉注释与空行**
后逐行比对。

为什么去掉注释：`nginx -T` 会把注释一起转储，而本次改造有意重写了注释（改成项目自己的
说明）。行为只取决于指令，因此比对指令序列；注释差异属预期。

用法：
    # 取基线（改造前的主配置）
    python .dsh/verify/nginx_config_golden.py web/nginx.conf .dsh/verify/nginx_baseline.txt
    # 取改造后（主配置 + 片段）
    python .dsh/verify/nginx_config_golden.py web/nginx.conf .dsh/verify/nginx_after.txt web/nginx-proxy-headers.conf
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def dump(raw_conf, snippet=None):
    """在 nginx 容器里转储生效配置；返回 (退出码, 配置转储, stderr)。

    用 `--entrypoint nginx` 绕开镜像自带的 entrypoint：否则它的日志会混进转储。
    """
    conf = os.path.abspath(raw_conf).replace("\\", "/")
    args = ["docker", "run", "--rm", "--entrypoint", "nginx",
            # proxy_pass 里的后端主机名只在 compose 网络内可解析，
            # 单独校验时给一条 hosts 映射，否则 nginx -t 会以 "host not found" 失败
            "--add-host", "43039infrasecurity-api:127.0.0.1",
            "-v", "%s:/etc/nginx/conf.d/default.conf:ro" % conf]
    if snippet:
        snippet_path = os.path.abspath(snippet).replace("\\", "/")
        args += ["-v", "%s:/etc/nginx/snippets/proxy-headers.conf:ro" % snippet_path]
    args += ["nginx:alpine", "-T"]

    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def directives(text):
    """只保留指令行：丢掉注释、空行与 nginx 自己加的文件分隔头。"""
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kept.append(stripped)
    return kept


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)

    conf, out_path = sys.argv[1], sys.argv[2]
    snippet = sys.argv[3] if len(sys.argv) > 3 else None

    code, output, errors = dump(conf, snippet)
    body = "\n".join(directives(output)) + "\n"

    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("exit=%d\n%s" % (code, body))

    print("exit=%d | 指令行数=%d | 写出 %s" % (code, len(directives(output)), out_path))
    if errors.strip():
        print("stderr:", errors.strip()[:300])


if __name__ == "__main__":
    main()
