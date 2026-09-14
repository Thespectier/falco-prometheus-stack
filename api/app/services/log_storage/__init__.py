"""日志 / 告警 / 事件 / 配置的持久化层。

实现按业务域拆在同一个包的多个模块里：

| 模块 | 职责 |
|---|---|
| `base` | 日志器、连接池、建表、游标生命周期 |
| `values` | 取值归一化与数据库行到接口结构的转换 |
| `config_kv` | 键值配置表 |
| `events` | events 表的写入与查询 |
| `alerts` | alerts 表的写入、查询与统计 |
| `incidents` | incidents 表的写入与查询 |
| `funnel` | 漏斗统计（日志 / 告警 / 事件） |
| `maintenance` | 过期数据清理与库维护 |
| `store` | 组合类与进程内单例 |

对外的导入路径保持不变：`from api.app.services.log_storage import log_storage`。
"""

from .base import LOG_STORAGE_DEBUG, logger
from .store import LogStorage, log_storage

__all__ = ["LOG_STORAGE_DEBUG", "LogStorage", "logger", "log_storage"]
