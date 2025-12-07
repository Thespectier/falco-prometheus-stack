from prometheus_client import generate_latest
from exporter import process_event

sample_event = {
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

process_event(sample_event)
process_event(sample_event)

metrics = generate_latest().decode("utf-8")
print("=== METRICS SAMPLE ===")
for line in metrics.splitlines():
    if line.startswith("syscall_events_total") or line.startswith("syscall_last_event_timestamp_seconds"):
        print(line)
print("=== END ===")

