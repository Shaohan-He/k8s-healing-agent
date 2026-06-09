"""告警数据模型"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AlertPayload(BaseModel):
    alert_name: str
    pod_name: str
    namespace: str
    severity: str  # critical | warning | info
    labels: dict = {}
    annotations: dict = {}
    starts_at: Optional[datetime] = None
    fingerprint: str = ""
