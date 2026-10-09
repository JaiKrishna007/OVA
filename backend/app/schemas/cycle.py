from datetime import date
from typing import Optional
from app.models.enums import CycleType, TrustStatus
from app.schemas.base import BaseReadSchema


class CycleRead(BaseReadSchema):
    id: str
    patient_id: str
    cycle_no: int
    type: CycleType
    start_date: date
    end_date: Optional[date] = None
    outcome: Optional[str] = None
    origin_org: Optional[str] = None
    external_cycle_no: Optional[str] = None
    source_id: Optional[str] = None
    org_id: Optional[str] = None
    trust_status: Optional[TrustStatus] = None
