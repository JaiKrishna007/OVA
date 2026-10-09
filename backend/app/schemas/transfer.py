from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import BaseReadSchema


class ExternalPatientDemographics(BaseModel):
    external_id: Optional[str] = Field(None, description="External clinic patient identifier")
    name: str = Field(..., description="Patient full name")
    dob: Optional[str] = Field(None, description="Date of birth YYYY-MM-DD")
    phone: Optional[str] = Field(None, description="Phone number")


class ImportUploadRequest(BaseModel):
    origin_org: str = Field(..., description="External hospital or clinic name")
    patient: ExternalPatientDemographics
    records: List[Dict[str, Any]] = Field(default_factory=list, description="Source records from external clinic")
    cycles: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Treatment cycles")
    treatment_events: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Treatment events")
    investigations: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Diagnostic investigations")


class ImportConfirmRequest(BaseModel):
    target_patient_id: str = Field(..., description="Internal patient ID to associate records with")
    confirm_identity: bool = Field(False, description="Explicit staff confirmation for medium/low confidence match")
    override_reasons: Optional[str] = Field(None, description="Clinical/staff rationale if overriding match warnings")


class ConsentCreateRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID")
    target_hospital_id: Optional[str] = Field(None, description="Target hospital ID granted consent")
    granted_to_hospital_id: Optional[str] = Field(None, description="Alias for target_hospital_id")
    purpose: str = Field("Continuity of fertility care", description="Purpose of consent")
    scope: str = Field("ALL_RECORDS", description="Scope of records covered")
    expires_at: Optional[datetime] = Field(None, description="Optional expiry timestamp")
    recorded_on_behalf: bool = Field(False, description="Flag indicating if hospital admin recorded on patient's behalf")
    consent_type: str = Field("external_transfer", description="Type of consent")
    granted_by: Optional[str] = Field(None, description="Consent granter name")
    status: str = Field("ACTIVE", description="ACTIVE | REVOKED | EXPIRED")


class ConsentRead(BaseReadSchema):
    id: str
    patient_id: str
    org_id: str
    granted_to_hospital_id: Optional[str] = None
    purpose: Optional[str] = "Continuity of fertility care"
    scope: Optional[str] = "ALL_RECORDS"
    consent_type: str = "external_transfer"
    status: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    granted_by: Optional[str] = None
    recorded_on_behalf: Optional[bool] = False
    created_at: Optional[datetime] = None


class TransferCreateRequest(BaseModel):
    patient_id: str = Field(..., description="Patient ID to transfer")
    from_hospital_id: Optional[str] = Field(None, description="Sending hospital ID (defaults to current hospital)")
    to_hospital_id: str = Field(..., description="Target receiving hospital ID")
    reason: Optional[str] = Field(None, description="Clinical or patient transfer reason")


class IdentityLinkRead(BaseReadSchema):
    id: str
    internal_patient_id: str
    external_patient_id: str
    external_org_name: str
    confidence_score: float
    status: str
    match_criteria_json: Optional[Any] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None


class ImportBatchRead(BaseReadSchema):
    id: str
    uploaded_by: str
    org_id: str
    origin_org: str
    status: str
    target_patient_id: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    validation_report_json: Optional[Any] = None
    identity_match_json: Optional[Any] = None
    cycle_suggestions_json: Optional[Any] = None
    raw_payload_json: Optional[Any] = None
