from typing import List
from sqlalchemy.orm import Session

from app.models.source_record import SourceRecord
from app.schemas.claims import Claim, ReasonCode


def check_span(db: Session, target_patient_id: str, claim: Claim) -> List[ReasonCode]:
    """
    Validates text span for note-supported claims:
    1. Span source record exists.
    2. Span offsets are valid and within source bounds.
    3. The extracted substring strictly contains the claim value.
    """
    if not claim.span:
        return []

    rec = db.get(SourceRecord, claim.span.record_id)
    if not rec:
        return [ReasonCode.SOURCE_NOT_FOUND]

    if rec.patient_id != target_patient_id:
        return [ReasonCode.PATIENT_SCOPE]

    content = rec.content_text or ""
    start, end = claim.span.start, claim.span.end

    if start < 0 or end < start or end > len(content):
        return [ReasonCode.SPAN_INVALID]

    substring = content[start:end]

    # Verify that the claimed value is actually contained in the span text
    if claim.value is not None:
        val_str = str(claim.value).strip().lower()
        if val_str not in substring.lower():
            return [ReasonCode.SPAN_INVALID]

    return []
