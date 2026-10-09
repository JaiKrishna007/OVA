from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.enums import ClaimValidationStatus


class CheckDetail(BaseModel):
    """Result of an individual deterministic extraction check."""
    name: str = Field(..., description="Unique check identifier")
    passed: bool = Field(..., description="Whether the check succeeded")
    detail: str = Field(..., description="Explanatory clinical or diagnostic message")
    reason_code: Optional[str] = Field(None, description="Standardized reason code if check failed")
    is_hard_check: bool = Field(True, description="Hard check failures reject; soft failures flag")


class ValidationResult(BaseModel):
    """Aggregate result of running ExtractionValidator on a candidate claim."""
    status: ClaimValidationStatus = Field(..., description="VERIFIED, REJECTED, or FLAGGED")
    checks: List[CheckDetail] = Field(default_factory=list, description="Detailed trace of all executed checks")
    reason_codes: List[str] = Field(default_factory=list, description="List of all triggered reason codes")
