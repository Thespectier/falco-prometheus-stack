from fastapi import APIRouter, HTTPException
import json
import os
from pathlib import Path
from api.app.core.config import settings

router = APIRouter()

@router.get("/{id}")
async def get_hbt_snapshot(id: str):
    """
    Get the latest HBT snapshot for a specific container.
    Reads from the shared storage path.
    """
    file_path = Path(settings.HBT_STORAGE_PATH) / f"{id}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"HBT snapshot not found for container {id}")
        
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read HBT snapshot: {str(e)}")
