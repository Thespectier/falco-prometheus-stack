import httpx
import time
from typing import Dict, Any, Optional
from api.app.core.config import settings

class PrometheusService:
    def __init__(self, base_url: str = settings.PROMETHEUS_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def query(self, query: str, time_ts: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute an instant query
        API: /api/v1/query
        """
        params = {"query": query}
        if time_ts:
            params["time"] = str(time_ts)
            
        try:
            response = await self.client.get("/api/v1/query", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}.")
            return {"status": "error", "errorType": "request_error", "error": str(exc)}
        except httpx.HTTPStatusError as exc:
            print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
            return {"status": "error", "errorType": "http_error", "error": str(exc)}

    async def query_range(self, query: str, start: float, end: float, step: int = 15) -> Dict[str, Any]:
        """
        Execute a range query
        API: /api/v1/query_range
        """
        params = {
            "query": query,
            "start": str(start),
            "end": str(end),
            "step": str(step)
        }
        
        try:
            response = await self.client.get("/api/v1/query_range", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def close(self):
        await self.client.aclose()

# Global instance
prometheus_service = PrometheusService()
