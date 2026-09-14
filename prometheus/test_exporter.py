"""exporter 的手工冒烟脚本。

造一条样本事件喂给 `process_event`，再把两个对外指标打印出来，用来确认
"事件 → 指标"这条链路在本地是通的——不需要 Falco，也不需要 Docker。

用法（在 `prometheus/` 目录下）：

    python test_exporter.py
"""

from prometheus_client import generate_latest

from exporter import process_event

# 只关心这两个指标；计数器与仪表的内建元数据不打印
WATCHED_METRICS = (
    "syscall_events_total",
    "syscall_last_event_timestamp_seconds",
)

# 样本事件：容器名、镜像、进程与一次 execve；时间用固定的 ISO8601，便于比对输出
SAMPLE_EVENT = {
    "rule": "process",
    "priority": "DEBUG",
    "output_fields": {
        "evt.type": "execve",
        "evt.time.iso8601": "2025-01-01T00:00:00Z",
        "container.name": "falco",
        "container.image.repository": "falcosecurity/falco",
        "proc.name": "bash",
        "k8s.ns.name": None,
        "k8s.pod.name": None
    }
}


def print_watched_metrics(metrics_text: str) -> None:
    """打印关注范围内的指标行。"""
    print("=== METRICS SAMPLE ===")
    for line in metrics_text.splitlines():
        if line.startswith(WATCHED_METRICS):
            print(line)
    print("=== END ===")


def main() -> None:
    """喂两次同一条事件（因此计数为 2），再打印指标。"""
    process_event(SAMPLE_EVENT)
    process_event(SAMPLE_EVENT)

    metrics = generate_latest().decode("utf-8")
    print_watched_metrics(metrics)


if __name__ == "__main__":
    main()
