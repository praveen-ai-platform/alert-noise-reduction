from datetime import datetime
from typing import List, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .alert_noise import reduce_alert_noise

app = FastAPI(title="Alert Noise Reduction POC", version="1.0.0")


class AlertEvent(BaseModel):
    alert_id: str
    service: str = Field(..., min_length=1)
    alert_name: str = Field(..., min_length=1)
    severity: Literal["info", "warning", "critical"]
    timestamp: datetime
    message: str = ""


class AlertReductionReq(BaseModel):
    alerts: List[AlertEvent]
    cooldown_minutes: int = Field(default=15, ge=0, le=1440)
    minimum_severity: Literal["info", "warning", "critical"] = "warning"

@app.get("/health")
def health():
    return {"status": "ok", "service": "alert-noise-reduction-poc"}


@app.post("/reduce-alert-noise")
def reduce_noise(req: AlertReductionReq):
    """Return actionable alerts after severity filtering and cooldown deduplication."""
    return reduce_alert_noise(
        (alert.model_dump(mode="json") for alert in req.alerts),
        cooldown_minutes=req.cooldown_minutes,
        minimum_severity=req.minimum_severity,
    )
