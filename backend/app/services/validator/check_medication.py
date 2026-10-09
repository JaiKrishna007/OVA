from typing import List, Optional
from app.schemas.claims import Claim, ReasonCode
from app.services.validator.resolver import ResolvedField
from app.models.clinical import Medication


def check_medication_match(claim: Claim, resolved_field: Optional[ResolvedField] = None) -> List[ReasonCode]:
    """
    Validates medication entity and attributes against database Medication records.
    """
    if not resolved_field or not isinstance(resolved_field.row, Medication):
        return []

    med: Medication = resolved_field.row

    # If claim specifies name, ensure it matches
    if resolved_field.column == "name" and claim.value:
        if str(claim.value).strip().lower() not in med.name.lower():
            return [ReasonCode.MEDICATION_MISMATCH]

    # If claim specifies dose, ensure it matches
    if resolved_field.column == "dose" and claim.value:
        if str(claim.value).strip().lower() != med.dose.strip().lower():
            return [ReasonCode.MEDICATION_MISMATCH]

    return []
