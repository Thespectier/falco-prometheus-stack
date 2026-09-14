"""大模型配置的读写。

API key 属于凭据：读取时只回掩码；写入时若前端回传的仍是掩码，视为"用户没有
改 key"，保持原值不动。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from api.app.services.log_storage import log_storage

router = APIRouter()

# 凭据掩码，前端据此判断是否需要覆盖
_MASK = "********"

_DEFAULT_ENDPOINT = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"

# 响应字段 → 存储键
_CONFIG_KEYS = {
    "api_key": "DEEPSEEK_API_KEY",
    "endpoint": "DEEPSEEK_ENDPOINT",
    "model": "DEEPSEEK_MODEL",
}


class LLMConfig(BaseModel):
    api_key: str = ""
    endpoint: str
    model: str


@router.get("/llm")
async def get_llm_config():
    """读取当前大模型配置，key 只回掩码。"""
    stored_key = log_storage.get_config(_CONFIG_KEYS["api_key"])

    return {
        "api_key": _MASK if stored_key else "",
        "endpoint": log_storage.get_config(_CONFIG_KEYS["endpoint"]) or _DEFAULT_ENDPOINT,
        "model": log_storage.get_config(_CONFIG_KEYS["model"]) or _DEFAULT_MODEL,
    }


@router.post("/llm")
async def set_llm_config(config: LLMConfig):
    """写入大模型配置；key 为空或仍是掩码时保持原值。"""
    if config.api_key and config.api_key != _MASK:
        log_storage.set_config(_CONFIG_KEYS["api_key"], config.api_key)

    log_storage.set_config(_CONFIG_KEYS["endpoint"], config.endpoint)
    log_storage.set_config(_CONFIG_KEYS["model"], config.model)
    return {"status": "ok"}
