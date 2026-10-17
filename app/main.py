from typing import Literal
from fastapi import Depends, FastAPI, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from .alert_noise import reduce_alert_noise
from .http_support import configure

Severity = Literal['info', 'warning', 'critical']

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Alert(StrictModel):
    alert_id: str = Field(min_length=1, max_length=128)
    environment: str = Field(default='production', min_length=1, max_length=64)
    service: str = Field(min_length=1, max_length=128)
    alert_name: str = Field(min_length=1, max_length=256)
    severity: Severity
    timestamp: AwareDatetime
    message: str = Field(default='', max_length=4096)

class Batch(StrictModel):
    alerts: list[Alert] = Field(max_length=1000)
    cooldown_minutes: int = Field(default=15, ge=0, le=1440)
    minimum_severity: Severity = 'warning'

    @model_validator(mode='after')
    def unique_ids(self):
        if len({a.alert_id for a in self.alerts}) != len(self.alerts):
            raise ValueError('alert_id must be unique within a batch')
        return self

class ActionableAlert(Alert):
    signature: list[str]

class SuppressedAlert(ActionableAlert):
    suppression_reason: Literal['below_minimum_severity', 'duplicate_within_cooldown']

class Summary(BaseModel):
    received: int
    actionable: int
    suppressed: int
    reduction_percent: float
    reasons: dict[str, int]

class ReductionResult(BaseModel):
    actionable_alerts: list[ActionableAlert]
    suppressed_alerts: list[SuppressedAlert]
    summary: Summary

def create_app():
    app = FastAPI(title='Alert Noise Reduction', version='2.0.0', description='Explainable, batch-scoped severity filtering and cooldown deduplication.')
    authenticate = configure(app)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'service': 'alert-noise-reduction'}

    @app.post('/reduce-alert-noise', response_model=ReductionResult, dependencies=[Depends(authenticate)])
    def reduce(batch: Batch):
        return reduce_alert_noise([a.model_dump(mode='json') for a in batch.alerts], batch.cooldown_minutes, batch.minimum_severity)
    return app

app = create_app()
