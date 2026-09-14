"""config 表：运行期的键值配置（大模型地址、凭据等）。

键值都是文本，读取方负责给默认值，因此这里不做任何解析与校验。
"""

from .base import LOG_STORAGE_DEBUG, logger

_INSERT_OR_UPDATE_SQL = """
    INSERT INTO config (key, value) VALUES (%s, %s)
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
"""


class ConfigKv:
    """键值配置读写。"""

    def get_config(self, key: str):
        """读一个配置项；缺失或查询失败返回 None。"""
        try:
            with self._read_cursor() as cursor:
                cursor.execute("SELECT value FROM config WHERE key = %s", (key,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as error:
            logger.error(f"Failed to get config {key}: {error}")
            return None

    def set_config(self, key: str, value: str):
        """写入或覆盖一个配置项。"""
        try:
            with self._write_cursor() as cursor:
                cursor.execute(_INSERT_OR_UPDATE_SQL, (key, value))
            if LOG_STORAGE_DEBUG:
                logger.info(f"Set config {key}")
        except Exception as error:
            logger.error(f"Failed to set config {key}: {error}")
