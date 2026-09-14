"""本子系统的日志器。

所有子模块共用同一个日志器名字（`hanabi.reducer`）：拆分模块不应该改变日志来源，
既有的日志检索、告警规则与排障手册都按这个名字过滤。
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hanabi.reducer")
