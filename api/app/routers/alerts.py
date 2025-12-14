from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from api.app.services.prometheus import prometheus_service

router = APIRouter()

@router.get("")
async def get_container_alerts(
    id: str,
    priority: Optional[str] = None
):
    """
    Get alerts statistics for a container.
    Derived from Prometheus metrics (high priority events).
    """
    # Construct query
    # Filter by priority if provided, otherwise default to high severity
    priority_filter = f'priority="{priority}"' if priority else 'priority=~"Warning|Error|Critical"'
    
    query = f'sum by (rule, priority) (rate(syscall_events_total{{container_name="{id}", {priority_filter}}}[5m]))'
    
    resp = await prometheus_service.query(query)
    
    alerts = []
    
    if resp.get("status") == "success":
        for item in resp.get("data", {}).get("result", []):
            alerts.append({
                "rule": item["metric"].get("rule", "unknown"),
                "priority": item["metric"].get("priority", "unknown"),
                "rate": float(item["value"][1])
            })
            
    return {
        "container_id": id,
        "alerts_stats": alerts,
        "note": "This returns statistical alert rates, not individual alert events."
    }
