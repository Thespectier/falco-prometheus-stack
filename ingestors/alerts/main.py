from fastapi import FastAPI, Body
from typing import Dict, Any
import os
from api.app.services.log_storage import log_storage

app = FastAPI(title="Alerts Ingestor", version="0.1.0")

@app.post("/alerts")
def ingest_alert(payload: Dict[str, Any] = Body(...)):
    output_fields = payload.get("output_fields", {})
    category = payload.get("category", "unknown")
    reason = payload.get("reason", "")
    attribute_value = payload.get("attribute_value", "")
    log_storage.add_alert(output_fields, category, reason, attribute_value)
    return {"status": "ok"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

