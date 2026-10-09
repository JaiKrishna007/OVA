"""
Pydantic read schemas for OVA v2 provenance, clinical claims, conflicts, gaps, and transfers.
"""

from datetime import date, datetime
from typing import Optional, Any, List
from app.models.enums import (
    ClaimValidationStatus,
    ExtractionMethod,
    ConflictStatus,
    GapStatus,
    TransferRequestStatus,
    HospitalAccessLevel,
    HospitalAccessStatus,
)
from app.schemas.base import BaseReadSchema


class ClinicalClaimRead(BaseReadSchema):
    id: str
    patient_id: str
    hospital_id: str
    source_record_id: str
    cycle_id: Optional[str] = None
    cycle_assignment: Optional[str] = "ASSIGNED"
    field: str
    value_text: Optional[str] = None
    value_num: Optional[float] = None
    unit: Optional[str] = None
    event_date: Optional[date] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    evidence_text: Optional[str] = None
    extraction_method: ExtractionMethod = ExtractionMethod.SEED
    validation_status: ClaimValidationStatus = ClaimValidationStatus.VERIFIED
    validation_checks: Optional[Any] = None
    reason_codes: Optional[Any] = None
    uploaded_by: Optional[str] = None
    created_at: datetime
    materialized_table: Optional[str] = None
    materialized_row_id: Optional[str] = None


class ConflictRead(BaseReadSchema):
    id: str
    patient_id: str
    field: str
    claim_ids: List[str]
    claim_a_id: Optional[str] = None
    claim_b_id: Optional[str] = None
    hospital_a: Optional[str] = None
    hospital_b: Optional[str] = None
    date_a: Optional[date] = None
    date_b: Optional[date] = None
    source_a: Optional[str] = None
    source_b: Optional[str] = None
    value_a: Optional[str] = None
    value_b: Optional[str] = None
    display_text: str = "Conflicting documented values. Clinician review required."
    status: ConflictStatus = ConflictStatus.OPEN
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    note: Optional[str] = None
    at: datetime


class ConflictAcknowledgeRequest(BaseReadSchema):
    note: Optional[str] = None


class DocumentationGapRead(BaseReadSchema):
    id: str
    patient_id: str
    cycle_id: Optional[str] = None
    rule_id: str
    trigger_claim_id: Optional[str] = None
    expected_item: str
    status: GapStatus = GapStatus.OPEN
    resolving_claim_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    note: Optional[str] = None
    detected_at: datetime


class GapAcknowledgeRequest(BaseReadSchema):
    note: Optional[str] = None


class TransferRequestRead(BaseReadSchema):
    id: str
    patient_id: str
    patient_name: Optional[str] = None
    from_hospital_id: str
    to_hospital_id: str
    requested_by: str
    status: TransferRequestStatus = TransferRequestStatus.REQUESTED
    consent_id: Optional[str] = None
    has_active_consent: Optional[bool] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class PatientHospitalAccessRead(BaseReadSchema):
    id: str
    patient_id: str
    hospital_id: str
    access_level: HospitalAccessLevel = HospitalAccessLevel.READ_ONLY
    status: HospitalAccessStatus = HospitalAccessStatus.ACTIVE
    source_transfer_id: Optional[str] = None
    since: datetime


class ConsentReadV2(BaseReadSchema):
    id: str
    patient_id: str
    org_id: str
    granted_to_hospital_id: Optional[str] = None
    purpose: Optional[str] = "transfer"
    scope: Optional[str] = "full_record"
    consent_type: str = "external_transfer"
    status: str = "ACTIVE"
    granted_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    granted_by: Optional[str] = None
    created_at: datetime
