"""事件速率的滑动窗口统计。

学习期的结束条件不是"等够时间"，而是"事件流安静下来"：窗口内不再有新事件，
说明该容器已经越过启动抖动阶段。计数器只保留最近一分钟的时间戳，并用它给出
窗口内的事件数。
"""

import time
from collections import deque

_MILLIS_PER_SECOND = 1000

# 速率窗口：计算结果只反映最近这一段时间的事件
RATE_WINDOW_MILLIS = 60 * _MILLIS_PER_SECOND


def _now_millis() -> int:
    return int(time.time() * _MILLIS_PER_SECOND)


class EventCounter:
    """按滑动窗口统计事件数，并记录学习期起点。"""

    def __init__(self, warmup_seconds: int = 3600):
        self.count = 0
        self.timestamps = deque()
        self.warmup_seconds = warmup_seconds
        self.start_time = _now_millis()

    def on_event(self) -> None:
        """记一次事件，并顺手把窗口外的旧时间戳清掉。"""
        self.timestamps.append(_now_millis())
        self.count += 1
        self.clean_expired_events()

    def clean_expired_events(self) -> None:
        """丢弃滑出窗口的时间戳。"""
        deadline = _now_millis() - RATE_WINDOW_MILLIS
        while self.timestamps and self.timestamps[0] < deadline:
            self.timestamps.popleft()
            self.count -= 1

    def is_warmup_period(self) -> bool:
        """是否仍在预热期（预热期内不做任何画像判定）。"""
        elapsed_millis = _now_millis() - self.start_time
        return elapsed_millis < self.warmup_seconds * _MILLIS_PER_SECOND

    def get_rate(self) -> int:
        """窗口内的事件数；窗口清空后自然归零，用于判定"安静下来"。"""
        return self.count
