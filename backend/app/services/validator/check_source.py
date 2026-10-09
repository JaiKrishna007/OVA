from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.source_record import SourceRecord
from app.schemas.claims import Claim, ReasonCode


def check_source_exists(db: Session, target_patient_id: str, claim: Claim) -> List[ReasonCode]:
    """
    Validates that:
    1. Every source_id in claim.source_ids exists in source_records (SOURCE_NOT_FOUND).
    2. Every source record belongs to the target patient (PATIENT_SCOPE).
    """
    reasons: List[ReasonCode] = []
    if not claim.source_ids:
        # ABSENCE claims without external source may reference detector rules
        if claim.type.value == "ABSENCE":
            return []
        return [ReasonCode.SOURCE_NOT_FOUND]

    for sid in claim.source_ids:
        rec = db.get(SourceRecord, sid)
        if not rec:
            if ReasonCode.SOURCE_NOT_FOUND not in reasons:
                reasons.append(ReasonCode.SOURCE_NOT_FOUND)
            continue
        if rec.patient_id != target_patient_id:
            if ReasonCode.PATIENT_SCOPE not in reasons:
                reasons.append(ReasonCode.PATIENT_SCOPE)

    return reasons
