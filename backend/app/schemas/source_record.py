from datetime import date
from typing import Optional
from app.models.enums import TrustStatus, SourceProcessingStatus
from app.schemas.base import BaseReadSchema


class SourceRecordRead(BaseReadSchema):
    id: str
    patient_id: str
    cycle_id: Optional[str] = None
    type: str
    date: date
    author: Optional[str] = None
    origin_org: str
    trust_status: TrustStatus
    content_text: str
    version: int
    uploaded_by: Optional[str] = None
    mime_type: Optional[str] = "text/plain"
    file_path: Optional[str] = None
    processing_status: Optional[SourceProcessingStatus] = SourceProcessingStatus.VALIDATED
    content_hash: Optional[str] = None


class RecordUploadResponse(BaseReadSchema):
    id: str
    patient_id: str
    cycle_id: Optional[str] = None
    type: str
    date: date
    author: Optional[str] = None
    origin_org: str
    trust_status: TrustStatus
    processing_status: SourceProcessingStatus
    content_hash: Optional[str] = None
    content_text: str
    file_path: Optional[str] = None
    warnings: list[str] = []
    message: str


class RecordStatusResponse(BaseReadSchema):
    id: str
    patient_id: str
    processing_status: SourceProcessingStatus
    mime_type: Optional[str] = None
    content_hash: Optional[str] = None
    type: str
    date: date
    author: Optional[str] = None
    origin_org: str
    warnings: list[str] = []
