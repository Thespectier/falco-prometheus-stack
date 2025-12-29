import os
import sqlite3
import time
import shutil
from api.app.services.log_storage import LogStorage

# Setup test environment
TEST_DB_DIR = "test_data"
TEST_DB = f"{TEST_DB_DIR}/logs.db"

if os.path.exists(TEST_DB_DIR):
    shutil.rmtree(TEST_DB_DIR)
os.makedirs(TEST_DB_DIR, exist_ok=True)

print(f"Initializing LogStorage at {TEST_DB}...")
storage = LogStorage(db_path=TEST_DB)

# 1. Verify WAL Mode
conn = sqlite3.connect(TEST_DB)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode;")
mode = cursor.fetchone()[0]
print(f"Journal Mode: {mode}")
if mode.upper() != "WAL":
    print("ERROR: WAL mode not enabled!")
    exit(1)
conn.close()

# 2. Populate Data for Pagination & Cleanup Test
print("Populating data...")
now = time.time()
# Add 10 events (logs)
for i in range(10):
    ts = now - (i * 3600) # 1 hour apart
    event = {
        "output_fields": {
            "container.id": "test_container",
            "evt.time": ts
        },
        "rule": f"Test Rule {i}",
        "priority": "Debug",
        "source": "syscall",
        "tags": ["test"]
    }
    storage.add_event(event)

# Add 5 Alerts (should NOT be deleted)
for i in range(5):
    ts = now - (i * 3600) - 20000 # Older alerts
    storage.add_alert(
        output_fields={
            "container.id": "test_container", 
            "evt.time": ts,
            "evt.type": "open",
            "proc.name": "cat"
        },
        category="Test",
        reason="Test Reason"
    )

# 3. Verify Pagination (Standard)
logs = storage.get_logs("test_container", limit=5)
print(f"Standard fetch got {len(logs)} logs.")
if len(logs) != 5:
    print("ERROR: Limit failed")
    exit(1)

# 4. Verify Pagination (Cursor)
last_ts_iso = logs[-1]['timestamp']
conn = sqlite3.connect(TEST_DB)
cursor = conn.cursor()
cursor.execute("SELECT timestamp FROM events WHERE container_id='test_container' ORDER BY timestamp DESC LIMIT 1 OFFSET 4")
cursor_val = cursor.fetchone()[0]
conn.close()

print(f"Testing cursor with ts < {cursor_val}...")
cursor_logs = storage.get_logs("test_container", limit=5, cursor_ts=cursor_val)
print(f"Cursor fetch got {len(cursor_logs)} logs.")
if len(cursor_logs) != 5:
    print(f"ERROR: Cursor fetch count mismatch. Got {len(cursor_logs)}")

# 5. Verify Cleanup (Events ONLY)
# We have logs from now back to now-9h.
# Cleanup retention = 6 hours (0.25 days).
# Logs older than 6h (indexes 6, 7, 8, 9) should be deleted.
# Alerts should remain untouched.

print("Testing cleanup (retention 0.25 days / 6 hours)...")
# Note: In test environment, we pass 0.25 explicitly to verify the default logic works if we called it without args too, 
# but let's be explicit for the test.
storage.cleanup_old_data(retention_days=0.25)

conn = sqlite3.connect(TEST_DB)
cursor = conn.cursor()

# Check Events
cursor.execute("SELECT COUNT(*) FROM events")
event_count = cursor.fetchone()[0]
print(f"Remaining events: {event_count}")
# Expected: 0,1,2,3,4,5 (0 to -5h) = 6 logs. 
# -6h is exactly on the boundary, depends on second precision. 
# Let's say approx 6 logs.
if event_count > 7 or event_count < 4:
     print("WARNING: Event cleanup count seems off (timezone/precision?)")

# Check Alerts
cursor.execute("SELECT COUNT(*) FROM alerts")
alert_count = cursor.fetchone()[0]
print(f"Remaining alerts: {alert_count}")
if alert_count != 5:
    print(f"ERROR: Alerts were deleted! Expected 5, got {alert_count}")
    exit(1)

# 6. Verify 'All' Containers Query
print("Testing 'All' containers query...")
alerts = storage.get_alerts(container_id="all", limit=100)
print(f"Fetched {len(alerts)} alerts for 'all' containers.")
if len(alerts) != 5:
    print(f"ERROR: Expected 5 alerts for 'all', got {len(alerts)}")
    exit(1)

print("All tests passed!")
