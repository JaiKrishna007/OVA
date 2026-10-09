from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator


class ClaimType(str, Enum):
    FACT = "FACT"
    ABSENCE = "ABSENCE"
    CONFLICT = "CONFLICT"


class Polarity(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"


class ValidationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"


class AssuranceTier(str, Enum):
    STRUCTURED_VERIFIED = "STRUCTURED_VERIFIED"
    NOTE_SUPPORTED = "NOTE_SUPPORTED"
    BLOCKED = "BLOCKED"


class ReasonCode(str, Enum):
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    PATIENT_SCOPE = "PATIENT_SCOPE"
    CYCLE_SCOPE = "CYCLE_SCOPE"
    DATE_MISMATCH = "DATE_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TEXT_NUMBER_MISMATCH = "TEXT_NUMBER_MISMATCH"
    MEDICATION_MISMATCH = "MEDICATION_MISMATCH"
    POLARITY_MISMATCH = "POLARITY_MISMATCH"
    SEVERITY_MISMATCH = "SEVERITY_MISMATCH"
    FIELD_PATH_INVALID = "FIELD_PATH_INVALID"
    SPAN_INVALID = "SPAN_INVALID"
    ACTIVE_CONFLICT = "ACTIVE_CONFLICT"
    ABSENCE_UNSUPPORTED = "ABSENCE_UNSUPPORTED"
    POLICY_VIOLATION = "POLICY_VIOLATION"


class TextSpan(BaseModel):
    record_id: str = Field(..., description="Source record ID containing text span")
    start: int = Field(..., ge=0, description="Start character offset")
    end: int = Field(..., ge=0, description="End character offset")


class Claim(BaseModel):
    claim_id: str = Field(..., description="Unique claim identifier, e.g. c12", examples=["c12"])
    type: ClaimType = Field(..., description="Claim type restricted to FACT, ABSENCE, CONFLICT", examples=["FACT"])
    section: str = Field(
        ...,
        description="Summary section (e.g. oocyte_retrieval, follicular_development, protocols_medications)",
        examples=["oocyte_retrieval"],
    )
    entity: str = Field(..., description="Clinical entity name", examples=["oocyte_retrieval"])
    cycle_id: Optional[str] = Field(None, description="Cycle ID if cycle-scoped", examples=["CY-P101-2"])
    field_path: Optional[str] = Field(
        None,
        description="Format: <table>.<row_id>.<column>",
        examples=["oocyte_retrievals.OPU-P101-2.oocytes_retrieved"],
    )
    value: Any = Field(None, description="Clinical value (int, float, str, or enum)", examples=[9])
    unit: Optional[str] = Field(None, description="Unit of measurement", examples=["pg/mL"])
    date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD", examples=["2024-06-12"])
    polarity: Polarity = Field(Polarity.PRESENT, description="Polarity: present or absent", examples=["present"])
    source_ids: List[str] = Field(default_factory=list, description="Referenced source record IDs", examples=[["REC-0051"]])
    span: Optional[TextSpan] = Field(None, description="Span offset for note-derived facts")
    display_text: str = Field(..., description="Human-readable claim presentation", examples=["Cycle 2 retrieved 9 oocytes."])
    
    # Metadata references for ABSENCE and CONFLICT
    absence_rule_id: Optional[str] = Field(None, description="Referenced Missing Data Detector rule_id")
    conflict_id: Optional[str] = Field(None, description="Referenced Conflict Detector conflict_id")

    @model_validator(mode="before")
    @classmethod
    def set_absence_polarity(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("type") in (ClaimType.ABSENCE, "ABSENCE") and "polarity" not in data:
                data["polarity"] = Polarity.ABSENT
        return data


class ClaimValidationResult(BaseModel):
    claim_id: str
    status: ValidationStatus
    assurance_tier: AssuranceTier
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    claim: Claim


class SectionValidationResult(BaseModel):
    section: str
    total_claims: int
    verified_claims: int
    blocked_claims: int
    blocked_ratio: float
    results: List[ClaimValidationResult] = Field(default_factory=list)


class ValidationReport(BaseModel):
    patient_id: str
    total_claims: int
    verified_claims: int
    blocked_claims: int
    blocked_ratio: float
    sections: Dict[str, SectionValidationResult] = Field(default_factory=dict)
    results: List[ClaimValidationResult] = Field(default_factory=list)
