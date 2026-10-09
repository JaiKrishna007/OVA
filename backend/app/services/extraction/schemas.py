from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class Span(BaseModel):
    """Exact character offset indices within raw document text."""
    start: int = Field(..., description="0-indexed start character offset (inclusive)")
    end: int = Field(..., description="0-indexed end character offset (exclusive)")


class CandidateClaim(BaseModel):
    """
    Candidate clinical claim extracted directly from an untrusted source document.
    Must adhere strictly to character span grounding.
    """
    field: str = Field(..., description="Clinical entity name (e.g. amh, fsh, opu, embryo_transfer)")
    value: Union[str, float, int] = Field(..., description="Extracted raw value or entity label")
    unit: Optional[str] = Field(None, description="Reported unit of measure (e.g. ng/mL, pg/mL, IU)")
    date: Optional[str] = Field(None, description="Event or specimen collection date as extracted")
    evidence_text: str = Field(..., description="Exact substring from document supporting this claim")
    span: Span = Field(..., description="Character offsets where evidence_text resides in document")
    confidence: Optional[float] = Field(None, description="Extraction confidence score (0.0 - 1.0)")


class CandidateClaimsResponse(BaseModel):
    """Model output payload wrapper."""
    claims: List[CandidateClaim] = []


class ExtractionResult(BaseModel):
    """Encapsulates raw extraction output along with safety and audit telemetry."""
    record_id: str
    claims: List[CandidateClaim] = []
    has_injection: bool = False
    guard_events: List[Dict[str, Any]] = []
    warnings: List[str] = []
    raw_text: str = ""


# Constrained JSON Schema for Gemini / LLM structured output
CANDIDATE_CLAIMS_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": ["string", "number"]},
                    "unit": {"type": ["string", "null"]},
                    "date": {"type": ["string", "null"]},
                    "evidence_text": {"type": "string"},
                    "span": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "integer"},
                            "end": {"type": "integer"},
                        },
                        "required": ["start", "end"],
                    },
                    "confidence": {"type": ["number", "null"]},
                },
                "required": ["field", "value", "evidence_text", "span"],
            },
        }
    },
    "required": ["claims"],
}
