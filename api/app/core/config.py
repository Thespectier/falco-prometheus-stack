"""运行期配置。

路径类配置一律走环境变量（由容器编排注入），默认值对应 Docker 网络内的地址；
本地直跑时用环境变量覆盖即可。字段名就是环境变量名，大小写敏感。
"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置项。"""

    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Falco/Hanabi Monitoring API"

    # Prometheus 查询地址：容器内按 compose 服务名解析
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")

    # HBT 快照的共享存储路径，与 hanabi 侧挂载同一个卷
    HBT_STORAGE_PATH: str = os.getenv("HBT_STORAGE_PATH", "/app/data/hbt")

    class Config:
        case_sensitive = True


settings = Settings()
