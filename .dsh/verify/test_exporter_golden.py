"""prometheus/test_exporter.py 的输出黄金验证。

该脚本是手工冒烟用：造一条样本事件喂给 exporter，然后把两个指标打印出来。验证方式就是
**原样跑它并比对 stdout**——脚本的输出格式（三个分隔标题 + 指标行）就是它唯一的产物。

环境要求：需要一个装了 prometheus_client 的解释器（`.dsh/verify/venv`）。
`docker` 用桩件替换（exporter 经由 hanabi.utils.queue 引入它，脚本本身用不到）。

归一化：prometheus_client 会给计数器附一行 `_created <时间戳>`，该时间戳是进程启动时刻，
因此统一替换成 `<TS>` 再比对。

运行：.dsh/verify/venv/Scripts/python.exe .dsh/verify/test_exporter_golden.py <输出文件>
"""

import contextlib
import io
import os
import re
import runpy
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(ROOT, "prometheus", "test_exporter.py")

# docker 桩：脚本链路里只有 hanabi.utils.queue 会 import docker
docker_module = types.ModuleType("docker")
docker_errors = types.ModuleType("docker.errors")


class DockerException(Exception):
    pass


class NotFound(DockerException):
    pass


docker_errors.DockerException = DockerException
docker_errors.NotFound = NotFound
docker_module.errors = docker_errors
docker_module.from_env = lambda *args, **kwargs: None
sys.modules["docker"] = docker_module
sys.modules["docker.errors"] = docker_errors

# 脚本用 `from exporter import process_event`，需要以 prometheus/ 为导入根
sys.path.insert(0, os.path.join(ROOT, "prometheus"))

buffer = io.StringIO()
error = None
try:
    with contextlib.redirect_stdout(buffer):
        runpy.run_path(SCRIPT, run_name="__main__")
except BaseException as exc:  # 脚本报错也是被观察的行为
    error = "%s: %s" % (type(exc).__name__, exc)

output = buffer.getvalue()
# 计数器自带的创建时间是进程启动时刻，替换成占位符
output = re.sub(r"^(\w+_created) [0-9.eE+-]+$", r"\1 <TS>", output, flags=re.MULTILINE)

payload = "ERROR: %s\n%s" % (error, output) if error else output

if len(sys.argv) > 1:
    with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
else:
    sys.stdout.write(payload)
