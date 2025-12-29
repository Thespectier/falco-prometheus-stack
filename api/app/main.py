from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from api.app.routers import containers, alerts, overview, hbt, stream, incidents, incidents_container, config

APP_PREFIX = "/infrasecurity"
ACCESS_CONTROL_ENABLED = os.getenv("ACCESS_CONTROL_ENABLED", "1").lower() not in {"0", "false", "no"}

app = FastAPI(
    title="Falco/Hanabi Monitoring API",
    description="API for container security monitoring and behavior modeling",
    version="0.1.0",
    docs_url=f"{APP_PREFIX}/docs",
    redoc_url=f"{APP_PREFIX}/redoc",
    openapi_url=f"{APP_PREFIX}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(alerts.router, prefix="/api/containers/{id}/alerts", tags=["alerts"])
app.include_router(overview.router, prefix="/api/overview", tags=["overview"])
app.include_router(hbt.router, prefix="/api/hbt", tags=["hbt"])
app.include_router(stream.router, prefix="/api/stream", tags=["stream"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(incidents_container.router, prefix="/api/containers/{id}/incidents", tags=["incidents"])
app.include_router(config.router, prefix="/api/config", tags=["config"])

app.include_router(containers.router, prefix=f"{APP_PREFIX}/api/containers", tags=["containers"])
app.include_router(alerts.router, prefix=f"{APP_PREFIX}/api/containers/{{id}}/alerts", tags=["alerts"])
app.include_router(overview.router, prefix=f"{APP_PREFIX}/api/overview", tags=["overview"])
app.include_router(hbt.router, prefix=f"{APP_PREFIX}/api/hbt", tags=["hbt"])
app.include_router(stream.router, prefix=f"{APP_PREFIX}/api/stream", tags=["stream"])
app.include_router(incidents.router, prefix=f"{APP_PREFIX}/api/incidents", tags=["incidents"])
app.include_router(incidents_container.router, prefix=f"{APP_PREFIX}/api/containers/{{id}}/incidents", tags=["incidents"])
app.include_router(config.router, prefix=f"{APP_PREFIX}/api/config", tags=["config"])

@app.get("/healthz")
@app.get(f"{APP_PREFIX}/healthz")
async def health_check():
    return {"status": "ok"}


@app.get("/clientsecurity/verifyToken")
@app.get(f"{APP_PREFIX}/clientsecurity/verifyToken")
async def verify_token(token: str | None = Query(default=None)):
    if not ACCESS_CONTROL_ENABLED:
        return {"success": True, "user": None}

    if not token:
        return {"success": False, "error": "缺少 token"}

    verify_url = "https://www.ideas.cnpc/api/common/v1/users/current?appCode=gx06hustinfrasecurity"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                verify_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": token,
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
        return {"success": False, "error": "验证接口连接失败"}
