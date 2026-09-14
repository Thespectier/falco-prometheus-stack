"""监控后端的 HTTP 入口。

每个路由模块挂两遍：不带前缀的（`/api/...`）给集群内部调用与前端默认配置用，
带业务前缀的（`/infrasecurity/api/...`）给接入网关之后的部署用。两套前缀来自
同一张挂载表，因此这里只描述一次"模块 → 路径 → 标签"。
"""

import os

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from api.app.routers import (
    alerts,
    config,
    containers,
    hbt,
    incidents,
    incidents_container,
    logs,
    overview,
    stream,
)

APP_PREFIX = "/infrasecurity"

# 关闭后 verifyToken 直接放行，供内网联调使用
ACCESS_CONTROL_ENABLED = os.getenv("ACCESS_CONTROL_ENABLED", "1").lower() not in {"0", "false", "no"}

# 网关校验地址；未配置时用生产默认值
_DEFAULT_VERIFY_URL = "https://www.ideas.cnpc/api/common/v1/users/current?appCode=gx06hustinfrasecurity"

# (路由模块, 挂载路径, 标签)。顺序即注册顺序，会体现在 OpenAPI 文档里。
_ROUTE_MOUNTS = (
    (containers, "/api/containers", "containers"),
    (alerts, "/api/containers/{id}/alerts", "alerts"),
    (overview, "/api/overview", "overview"),
    (hbt, "/api/hbt", "hbt"),
    (stream, "/api/stream", "stream"),
    (incidents, "/api/incidents", "incidents"),
    (incidents_container, "/api/containers/{id}/incidents", "incidents"),
    (config, "/api/config", "config"),
    (logs, "/api/logs", "logs"),
)

app = FastAPI(
    title="Falco/Hanabi Monitoring API",
    description="API for container security monitoring and behavior modeling",
    version="0.1.0",
    docs_url=f"{APP_PREFIX}/docs",
    redoc_url=f"{APP_PREFIX}/redoc",
    openapi_url=f"{APP_PREFIX}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 生产环境按实际前端域名收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _router_module, _mount_path, _tag in _ROUTE_MOUNTS:
    app.include_router(_router_module.router, prefix=_mount_path, tags=[_tag])

# 同一批路由再挂一遍带业务前缀的路径
for _router_module, _mount_path, _tag in _ROUTE_MOUNTS:
    app.include_router(_router_module.router, prefix=f"{APP_PREFIX}{_mount_path}", tags=[_tag])


@app.get("/healthz")
@app.get(f"{APP_PREFIX}/healthz")
async def health_check():
    """存活探针：只表示进程可服务，不代表下游依赖健康。"""
    return {"status": "ok"}


@app.get("/clientsecurity/verifyToken")
@app.get(f"{APP_PREFIX}/clientsecurity/verifyToken")
async def verify_token(token: str | None = Query(default=None)):
    """按网关要求校验前端携带的 token，并回传当前用户信息。"""
    if not ACCESS_CONTROL_ENABLED:
        return {"success": True, "user": None}

    if not token:
        return {"success": False, "error": "缺少 token"}

    verify_url = os.getenv("VERIFY_TOKEN_URL", _DEFAULT_VERIFY_URL)

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(
                verify_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            remote_json = resp.json()

        if remote_json.get("code") != 0:
            return {
                "success": False,
                "error": remote_json.get("message") or "token 无效",
            }

        return {"success": True, "user": remote_json.get("data")}
    except Exception:
        # 网关不可达与 token 无效对前端是两种提示，必须区分开
        return {"success": False, "error": "验证接口连接失败"}
