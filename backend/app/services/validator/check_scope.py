from typing import List, Optional
from app.schemas.claims import Claim, ReasonCode
from app.services.validator.resolver import ResolvedField


def check_scope(
    target_patient_id: str,
    claim: Claim,
    resolved_field: Optional[ResolvedField] = None,
) -> List[ReasonCode]:
    """
    Validates patient scope and cycle scope on the resolved field:
    1. resolved_field.patient_id must match target_patient_id (PATIENT_SCOPE).
    2. claim.cycle_id must match resolved_field.cycle_id if cycle-scoped (CYCLE_SCOPE).
    """
    reasons: List[ReasonCode] = []

    if resolved_field:
        if resolved_field.patient_id and resolved_field.patient_id != target_patient_id:
            reasons.append(ReasonCode.PATIENT_SCOPE)

        if claim.cycle_id and resolved_field.cycle_id:
            if claim.cycle_id != resolved_field.cycle_id:
                reasons.append(ReasonCode.CYCLE_SCOPE)

    return reasons
