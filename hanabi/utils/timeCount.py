import time
from collections import deque

class EventCounter:
    def __init__(self, warmup_seconds=45):
        self.count = 0
        self.timestamps = deque()
        self.warmup_seconds = warmup_seconds  # 预热时间（秒）
        self.start_time = int(time.time() * 1000)  # 初始化时间戳（毫秒）

    def on_event(self):
        now = int(time.time() * 1000)  # 当前时间戳（毫秒）
        self.timestamps.append(now)
        self.count += 1

        self.clean_expired_events()

    def clean_expired_events(self):
        now = int(time.time() * 1000)
        while self.timestamps and now - self.timestamps[0] > 1000 * 60:
            self.timestamps.popleft()
            self.count -= 1

    def is_warmup_period(self):
        """判断是否还在预热期"""
        now = int(time.time() * 1000)
        elapsed_seconds = (now - self.start_time) / 1000
        return elapsed_seconds < self.warmup_seconds

    def get_rate(self):
        return self.count  # 当前10秒内的事件数
