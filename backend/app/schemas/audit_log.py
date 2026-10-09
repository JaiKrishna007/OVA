from datetime import datetime
from typing import Optional, Any
from app.schemas.base import BaseReadSchema


class AuditLogRead(BaseReadSchema):
    id: str
    org_id: Optional[str] = None
    hospital_id: Optional[str] = None
    user_id: str
    action: str
    patient_id: Optional[str] = None
    event_type: Optional[str] = None
    details: Optional[Any] = None
    outcome: Optional[str] = "success"
    at: datetime
