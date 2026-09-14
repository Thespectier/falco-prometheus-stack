"""HBT 快照读取。

快照由 hanabi 侧定期落盘到共享卷，后端只负责读取与错误翻译，不解析其内部结构，
这样 hanabi 侧调整树结构不需要同步改后端。
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.app.core.config import settings

router = APIRouter()


@router.get("/{id}")
async def get_hbt_snapshot(id: str):
    """读取某容器最新的 HBT 快照。"""
    snapshot_path = Path(settings.HBT_STORAGE_PATH) / f"{id}.json"

    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail=f"HBT snapshot not found for container {id}")

    try:
        with open(snapshot_path, "r") as handle:
            return json.load(handle)
    except Exception as error:
        # 落盘过程中被读到半截文件是常见情况，按 5xx 返回让前端稍后重试
        raise HTTPException(status_code=500, detail=f"Failed to read HBT snapshot: {str(error)}")
