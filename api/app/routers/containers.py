from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from api.app.services.prometheus import prometheus_service
from api.app.services.log_storage import log_storage

router = APIRouter()

@router.get("")
async def list_containers():
    """
    List all monitored containers with their current status and metrics.
    Derived from Prometheus metrics.
    """
    # Query for last event timestamp to get list of containers
    last_seen_query = "syscall_last_event_timestamp_seconds"
    # Query for current event rate
    rate_query = "sum by (container_name) (rate(syscall_events_total[5m]))"
    
    last_seen_resp = await prometheus_service.query(last_seen_query)
    rate_resp = await prometheus_service.query(rate_query)
    
    containers = {}
    
    # Process last seen
    if last_seen_resp.get("status") == "success":
        for item in last_seen_resp.get("data", {}).get("result", []):
            name = item["metric"].get("container_name")
            if name:
                containers[name] = {
                    "id": name, # using name as ID for now
                    "name": name,
                    "last_seen": float(item["value"][1]),
                    "event_rate": 0.0
                }
                
    # Process rates
    if rate_resp.get("status") == "success":
        for item in rate_resp.get("data", {}).get("result", []):
            name = item["metric"].get("container_name")
            if name and name in containers:
                containers[name]["event_rate"] = float(item["value"][1])
                
    return list(containers.values())

@router.get("/{id}/logs")
async def get_container_logs(
    id: str, 
    start: Optional[int] = None, 
    end: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get historical logs for a container from SQLite storage.
    """
    logs = log_storage.get_logs(container_id=id, limit=limit, offset=offset)
    
    return {
        "container_id": id,
        "logs": logs
    }
