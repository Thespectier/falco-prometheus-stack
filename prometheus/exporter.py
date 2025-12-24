from prometheus_client import start_http_server, Counter, Gauge
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from hanabi.utils.queue import DockerLogQueue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


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

def _get_rule_category(rule: str, evt_type: str) -> str:
    r = (rule or '').lower()
    if r in ('process', 'proc'):
        return 'process'
    if r in ('network', 'net'):
        return 'network'
    if r == 'file':
        return 'file'
    t = (evt_type or '').lower()
    if t in ('execve', 'clone', 'fork', 'vfork'):
        return 'process'
    if t in ('connect', 'accept', 'send', 'recv', 'sendto', 'recvfrom', 'listen', 'bind'):
        return 'network'
    if t in ('open', 'openat', 'close', 'read', 'write', 'unlink', 'unlinkat'):
        return 'file'
    return 'unknown'


def _parse_event_timestamp(output_fields):
    ts_iso = output_fields.get('evt.time.iso8601')
    if isinstance(ts_iso, str):
        try:
            dt = datetime.fromisoformat(ts_iso.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except Exception:
            pass
    ts = output_fields.get('evt.time')
    if isinstance(ts, (int, float)):
        if ts > 1e12:
            return int(ts / 1e9)
        if ts > 1e9:
            return int(ts / 1e6)
        return int(ts)
    return int(datetime.utcnow().timestamp())


def process_event(event_data):
    try:
        output_fields = event_data.get('output_fields', {})
        
        # 提取标签值，为缺失的值提供默认 'unknown'
        rule = event_data.get('rule', 'unknown')
        priority = event_data.get('priority', 'unknown')
        container_name = output_fields.get('container.name', 'unknown')
        if container_name != 'unknown':
            image_repository = output_fields.get('container.image.repository', 'unknown')
            process_name = output_fields.get('proc.name', 'unknown')
            evt_type = output_fields.get('evt.type', 'unknown')
            
            k8s_namespace = output_fields.get('k8s.ns.name') or 'none'
            k8s_pod = output_fields.get('k8s.pod.name') or 'none'

            SYSCALL_EVENTS.labels(
                rule=rule,
                priority=priority,
                container_name=container_name,
                image_repository=image_repository,
                process_name=process_name,
                k8s_namespace=k8s_namespace,
                k8s_pod=k8s_pod,
                rule_category=_get_rule_category(rule, evt_type)
            ).inc()

            ts_sec = _parse_event_timestamp(output_fields)
            LAST_EVENT_TIMESTAMP.labels(container_name=container_name).set(ts_sec)

            logging.info(f"Processed event from container: {container_name}, rule: {rule}")

    except Exception as e:
        logging.error(f"Error processing event: {e}\nData: {event_data}")


def consume_events(container_name="falco"):
    """从 DockerLogQueue 持续消费事件"""
    log_queue = None
    try:
        logging.info(f"Starting to consume events from container: {container_name}")
        log_queue = DockerLogQueue(container_name=container_name, max_queue_size=10000)
        log_queue.start()
        
        while True:
            json_obj = log_queue.get(timeout=1)
            if json_obj:
                process_event(json_obj)
                pass
                
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
    metrics_port = 9876
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
