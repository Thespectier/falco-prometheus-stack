"""Falco 事件 → Prometheus 指标。

从 Falco 容器的日志里读 JSON 事件，折算成指标：事件总量按规则/优先级/容器/镜像/
进程等维度计数，另外记录每个容器最近一次事件的时间戳，供总览页与告警查询使用。

指标名与标签顺序是对外契约（Prometheus 抓取、Grafana 看板、总览页的 PromQL 都按
这些名字写死），因此只新增不改名。
"""

import logging
import os
import sys
from datetime import datetime

from prometheus_client import Counter, Gauge, start_http_server

# 直接以脚本方式运行时（python prometheus/exporter.py）需要能 import hanabi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hanabi.utils.queue import DockerLogQueue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 标签顺序即 /metrics 上的暴露顺序
EVENT_LABELS = [
    'rule', 'priority', 'container_name',
    'image_repository', 'process_name', 'k8s_namespace', 'k8s_pod',
    'rule_category'
]

SYSCALL_EVENTS = Counter('syscall_events_total', 'Total number of syscall events observed.', EVENT_LABELS)

LAST_EVENT_TIMESTAMP = Gauge(
    'syscall_last_event_timestamp_seconds',
    'Timestamp (seconds) of the last processed syscall event.',
    ['container_name']
)

EVENT_RATE_10S = Gauge(
    'syscall_event_rate_10s',
    'Event rate in last 10 seconds window.',
    ['container_name']
)

# 规则名 → 分类
_RULE_CATEGORIES = {
    'process': 'process',
    'proc': 'process',
    'network': 'network',
    'net': 'network',
    'file': 'file',
}

# 内核事件类型 → 分类
_EVENT_TYPE_CATEGORIES = {
    'execve': 'process',
    'clone': 'process',
    'fork': 'process',
    'vfork': 'process',
    'connect': 'network',
    'accept': 'network',
    'send': 'network',
    'recv': 'network',
    'sendto': 'network',
    'recvfrom': 'network',
    'listen': 'network',
    'bind': 'network',
    'open': 'file',
    'openat': 'file',
    'close': 'file',
    'read': 'file',
    'write': 'file',
    'unlink': 'file',
    'unlinkat': 'file',
}

# evt.time 的量级分界：大于纳秒阈值按纳秒、大于毫秒阈值按毫秒，其余按秒
_NANOSECOND_THRESHOLD = 1e12
_MILLISECOND_THRESHOLD = 1e9

_DEFAULT_METRICS_PORT = 9876
_QUEUE_READ_TIMEOUT_SECONDS = 1
_MAX_QUEUE_SIZE = 100000


def _get_rule_category(rule: str, evt_type: str) -> str:
    """判定事件属于哪一类行为：优先看规则名，其次看内核事件类型。"""
    category = _RULE_CATEGORIES.get((rule or '').lower())
    if category:
        return category
    return _EVENT_TYPE_CATEGORIES.get((evt_type or '').lower(), 'unknown')


def _parse_event_timestamp(output_fields):
    """取事件时间（Unix 秒）。

    优先用 ISO8601 字符串；回退到数值型 evt.time，按量级推断单位；两者都没有时
    用当前时间，宁可时间不精确也不能让指标缺时间戳。
    """
    iso_value = output_fields.get('evt.time.iso8601')
    if isinstance(iso_value, str):
        try:
            dt = datetime.fromisoformat(iso_value.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except Exception:
            pass

    raw_value = output_fields.get('evt.time')
    if isinstance(raw_value, (int, float)):
        if raw_value > _NANOSECOND_THRESHOLD:
            return int(raw_value / 1e9)
        if raw_value > _MILLISECOND_THRESHOLD:
            return int(raw_value / 1e6)
        return int(raw_value)

    return int(datetime.utcnow().timestamp())


def _event_labels(rule: str, priority: str, output_fields, container_name: str) -> dict:
    """整理指标标签值，缺失项按声明兜底为 unknown / none。"""
    return {
        'rule': rule,
        'priority': priority,
        'container_name': container_name,
        'image_repository': output_fields.get('container.image.repository', 'unknown'),
        'process_name': output_fields.get('proc.name', 'unknown'),
        'k8s_namespace': output_fields.get('k8s.ns.name') or 'none',
        'k8s_pod': output_fields.get('k8s.pod.name') or 'none',
        'rule_category': _get_rule_category(rule, output_fields.get('evt.type', 'unknown')),
    }


def process_event(event_data):
    """处理一条事件：计数 + 刷新该容器的时间戳。"""
    try:
        output_fields = event_data.get('output_fields', {})
        rule = event_data.get('rule', 'unknown')
        priority = event_data.get('priority', 'unknown')
        container_name = output_fields.get('container.name', 'unknown')

        if container_name == 'unknown':
            # 宿主机事件等拿不到容器名的情况不进指标，否则会污染按容器的聚合
            return

        SYSCALL_EVENTS.labels(**_event_labels(rule, priority, output_fields, container_name)).inc()
        LAST_EVENT_TIMESTAMP.labels(container_name=container_name).set(_parse_event_timestamp(output_fields))

        logging.info(f"Processed event from container: {container_name}, rule: {rule}")

    except Exception as e:
        logging.error(f"Error processing event: {e}\nData: {event_data}")


def consume_events(container_name="falco"):
    """持续消费容器日志，直到被中断。"""
    log_queue = None
    try:
        logging.info(f"Starting to consume events from container: {container_name}")
        log_queue = DockerLogQueue(container_name=container_name, max_queue_size=_MAX_QUEUE_SIZE)
        log_queue.start()

        while True:
            json_obj = log_queue.get(timeout=_QUEUE_READ_TIMEOUT_SECONDS)
            if json_obj:
                process_event(json_obj)

    except KeyboardInterrupt:
        logging.info("Stopping event consumer...")
    except Exception as e:
        logging.error(f"Error in event consumer: {e}")
    finally:
        if log_queue:
            log_queue.stop()
            stats = log_queue.get_stats()
            logging.info(f"Final stats: {stats}")


if __name__ == '__main__':
    metrics_port = _DEFAULT_METRICS_PORT
    container_name = os.getenv('FALCO_CONTAINER', 'falco')

    logging.info(f"Metrics endpoint: http://0.0.0.0:{metrics_port}/metrics")
    logging.info(f"Consuming events from container: {container_name}")
    logging.info("=" * 60)

    start_http_server(metrics_port)
    logging.info(f"✅ Prometheus metrics server started on port {metrics_port}")

    try:
        consume_events(container_name=container_name)
    except KeyboardInterrupt:
        logging.info("\n🛑 Exporter stopped by user")
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        sys.exit(1)
