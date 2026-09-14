"""把 Docker 容器的日志流变成一个可消费的 JSON 队列。

Falco 以 JSON 行输出事件。这里挂一个后台线程持续跟随容器的日志，按行切分并把解析
成功的对象放进队列；调用方（exporter / worker / 回放脚本）只管从队列取，不关心
读取与解析。

行数与 JSON 错误数会记下来供退出时打印：Falco 输出被截断或混入非 JSON 行时，最先
体现在 JSON 错误数上，是排障的第一入口。
"""

import json
import sys
from datetime import datetime
from queue import Queue
from threading import Event, Thread

import docker

# 停止时等待后台线程收尾的时间上限
_JOIN_TIMEOUT_SECONDS = 2

# 默认队列上限：足够吸收一轮突发，同时避免内存无界增长
_DEFAULT_MAX_QUEUE_SIZE = 100000


class DockerLogQueue:
    """在后台线程里跟随读取某个容器的日志，把 JSON 行放进队列。"""

    def __init__(self, container_name="falco", max_queue_size=_DEFAULT_MAX_QUEUE_SIZE):
        self.container_name = container_name
        self.queue = Queue(maxsize=max_queue_size)
        self.stop_event = Event()
        self.thread = None
        self.client = None
        self.container = None
        self.line_count = 0
        self.error_count = 0

    def start(self):
        """连接容器并启动后台读取线程。"""
        self._connect()

        self.thread = Thread(target=self._stream_logs, daemon=True)
        self.thread.start()
        print(f"✅ Log streaming started", file=sys.stderr)

    def _connect(self):
        """建立 Docker 客户端并定位容器。

        两种失败给同一类异常：容器不存在在 SDK 里也是 DockerException 的子类，
        因此统一报"连不上 daemon"更符合实际排查路径（先看 daemon 与名字）。
        """
        try:
            self.client = docker.from_env()
            self.container = self.client.containers.get(self.container_name)
            print(f"✅ Connected to container '{self.container_name}' (ID: {self.container.short_id})", file=sys.stderr)
        except docker.errors.DockerException as e:
            raise Exception(f"Failed to connect to Docker daemon: {e}")
        except docker.errors.NotFound:
            raise Exception(f"Container '{self.container_name}' not found")

    def _stream_logs(self):
        """后台线程主体：跟随日志流，按行切分后交给 _ingest_line。"""
        log_stream = self.container.logs(
            stream=True,
            follow=True,
            stdout=True,
            stderr=False,
            since=int(datetime.now().timestamp()),
        )
        buffer = ""

        try:
            for chunk in log_stream:
                if self.stop_event.is_set():
                    break

                try:
                    buffer += chunk.decode('utf-8')
                except (KeyboardInterrupt, SystemExit):
                    break

                # 一个 chunk 可能含多行，也可能只有半行：只有见到换行才处理
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    self._ingest_line(line)
        except Exception as e:
            if not self.stop_event.is_set():
                print(f"❌ Error in log streaming: {e}", file=sys.stderr)

    def _ingest_line(self, line: str):
        """处理一整行：空行跳过；解析成功入队，失败只计数。"""
        if not line.strip():
            return

        self.line_count += 1
        try:
            self.queue.put(json.loads(line))
        except json.JSONDecodeError as e:
            self.error_count += 1
            print(f"Invalid JSON on line {self.line_count}: {e}", file=sys.stderr)

    def get(self, timeout=None):
        """取一个对象；超时或队列为空时返回 None。"""
        try:
            return self.queue.get(timeout=timeout)
        except:  # noqa: E722 - 空队列与超时都按"这次没有数据"处理
            return None

    def get_nowait(self):
        """不阻塞地取一个对象，没有则返回 None。"""
        try:
            return self.queue.get_nowait()
        except:
            return None

    def size(self):
        """当前积压条数。"""
        return self.queue.qsize()

    def is_empty(self):
        """队列是否为空。"""
        return self.queue.empty()

    def get_stats(self):
        """排障统计：已处理行数、JSON 错误数、当前积压。"""
        return {
            "lines_processed": self.line_count,
            "json_errors": self.error_count,
            "queue_size": self.queue.qsize()
        }

    def stop(self):
        """停止后台线程并打印统计。"""
        print(f"\n🛑 Stopping log stream...", file=sys.stderr)
        self.stop_event.set()

        if self.thread:
            self.thread.join(timeout=_JOIN_TIMEOUT_SECONDS)

        stats = self.get_stats()
        print(f"📊 Stats: {stats['lines_processed']} lines, {stats['json_errors']} errors", file=sys.stderr)
