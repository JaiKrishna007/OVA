from datetime import datetime
from typing import Optional, Any
from app.schemas.base import BaseReadSchema


class SummaryFeedbackRead(BaseReadSchema):
    id: str
    summary_id: str
    statement_ref: str
    type: str
    comment: Optional[str] = None
    user_id: str
    at: datetime


class SummaryRead(BaseReadSchema):
    id: str
    patient_id: str
    version: int
    data_version: str
    generated_at: datetime
    content_json: Any
    validator_report_json: Any
