from fastapi import APIRouter, HTTPException
from api.app.services.prometheus import prometheus_service
import time

router = APIRouter()

@router.get("")
async def get_overview():
    """
    Get system overview metrics:
    - Total event rate
    - Distribution by priority
    - Distribution by category
    - Active containers count
    """
    now = time.time()
    
    # Define queries
    queries = {
        "total_rate": 'sum(rate(syscall_events_total[5m]))',
        "by_priority": 'sum by(priority) (rate(syscall_events_total[5m]))',
        "by_category": 'sum by(rule_category) (rate(syscall_events_total[5m]))',
        "active_containers": 'count(sum by(container_name) (rate(syscall_events_total[5m]) > 0))'
    }
    
    results = {}
    
    for key, query in queries.items():
        resp = await prometheus_service.query(query)
        if resp.get("status") == "success":
            data = resp.get("data", {}).get("result", [])
            results[key] = data
        else:
            # Log error but continue with partial results or empty
            results[key] = []

    # Format response
    formatted_response = {
        "total_events_rate": 0.0,
        "priority_distribution": [],
        "category_distribution": [],
        "active_containers_count": 0
    }

    # Process total_rate
    if results["total_rate"]:
        try:
            formatted_response["total_events_rate"] = float(results["total_rate"][0]["value"][1])
        except (IndexError, ValueError):
            pass

    # Process by_priority
    for item in results["by_priority"]:
        try:
            formatted_response["priority_distribution"].append({
                "priority": item["metric"].get("priority", "unknown"),
                "value": float(item["value"][1])
            })
        except (ValueError, KeyError):
            pass

    # Process by_category
    for item in results["by_category"]:
        try:
            formatted_response["category_distribution"].append({
                "category": item["metric"].get("rule_category", "unknown"),
                "value": float(item["value"][1])
            })
        except (ValueError, KeyError):
            pass

    # Process active_containers
    if results["active_containers"]:
        try:
            formatted_response["active_containers_count"] = int(results["active_containers"][0]["value"][1])
        except (IndexError, ValueError):
            pass

    return formatted_response
