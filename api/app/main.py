from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.app.routers import containers, alerts, overview, hbt, stream, incidents, incidents_container

app = FastAPI(
    title="Falco/Hanabi Monitoring API",
    description="API for container security monitoring and behavior modeling",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}
