"""LogStorage 的组合与进程内单例。

各方法按业务域拆在 mixin 里，组合类本身不实现逻辑，只把能力拼成一个对象。对外的
方法与签名与拆分前完全一致，调用方（路由、ingestors、reducer、analyzer）无需改动。
"""

from .alerts import AlertStore
from .base import LOG_STORAGE_DEBUG, DatabaseBacked, logger
from .config_kv import ConfigKv
from .events import EventStore
from .funnel import FunnelStats
from .incidents import IncidentStore
from .maintenance import Maintenance


class LogStorage(
    ConfigKv,
    EventStore,
    AlertStore,
    IncidentStore,
    FunnelStats,
    Maintenance,
    DatabaseBacked,
):
    """日志 / 告警 / 事件 / 配置的持久化入口。"""


log_storage = LogStorage()

__all__ = ["LOG_STORAGE_DEBUG", "LogStorage", "logger", "log_storage"]
