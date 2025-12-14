import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Falco/Hanabi Monitoring API"
    
    # Prometheus Configuration
    PROMETHEUS_URL: str = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    
    # HBT Storage Configuration
    HBT_STORAGE_PATH: str = os.getenv("HBT_STORAGE_PATH", "/app/data/hbt")
    
    class Config:
        case_sensitive = True

settings = Settings()
