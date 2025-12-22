from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.app.services.log_storage import log_storage

router = APIRouter()

class LLMConfig(BaseModel):
    api_key: str
    endpoint: str
    model: str

@router.get("/llm")
async def get_llm_config():
    return {
        "api_key": log_storage.get_config("DEEPSEEK_API_KEY") or "",
        "endpoint": log_storage.get_config("DEEPSEEK_ENDPOINT") or "https://api.deepseek.com",
        "model": log_storage.get_config("DEEPSEEK_MODEL") or "deepseek-chat"
    }

@router.post("/llm")
async def set_llm_config(config: LLMConfig):
    log_storage.set_config("DEEPSEEK_API_KEY", config.api_key)
    log_storage.set_config("DEEPSEEK_ENDPOINT", config.endpoint)
    log_storage.set_config("DEEPSEEK_MODEL", config.model)
    return {"status": "ok"}
