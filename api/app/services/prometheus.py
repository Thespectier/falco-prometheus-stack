"""Prometheus 查询客户端。

两个入口对应 Prometheus 的 instant query 与 range query。`query` 对网络类错误做了
分类返回，调用方据此区分"查询失败"与"确实没有数据"；`query_range` 目前只有粗粒度
错误处理，因为总览页只用前者。
"""

from typing import Any, Dict, Optional

import httpx

from api.app.core.config import settings

_INSTANT_QUERY_PATH = "/api/v1/query"
_RANGE_QUERY_PATH = "/api/v1/query_range"


class PrometheusService:
    """按 base_url 复用一个异步 HTTP 客户端。"""

    def __init__(self, base_url: str = settings.PROMETHEUS_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def query(self, query: str, time_ts: Optional[float] = None) -> Dict[str, Any]:
        """执行 instant query；给定 time_ts 时查该时刻的值。"""
        params = {"query": query}
        if time_ts:
            params["time"] = str(time_ts)

        try:
            response = await self.client.get(_INSTANT_QUERY_PATH, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}.")
            return {"status": "error", "errorType": "request_error", "error": str(exc)}
        except httpx.HTTPStatusError as exc:
            print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
            return {"status": "error", "errorType": "http_error", "error": str(exc)}

    async def query_range(self, query: str, start: float, end: float, step: int = 15) -> Dict[str, Any]:
        """执行 range query；start/end 是 Unix 秒。"""
        params = {
            "query": query,
            "start": str(start),
            "end": str(end),
            "step": str(step),
        }

        try:
            response = await self.client.get(_RANGE_QUERY_PATH, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def close(self):
        """释放底层连接，供进程退出时调用。"""
        await self.client.aclose()


prometheus_service = PrometheusService()
