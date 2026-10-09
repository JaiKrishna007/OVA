from datetime import date
from typing import List, Optional
from app.schemas.claims import Claim, ReasonCode
from app.services.validator.resolver import ResolvedField


def check_date_match(claim: Claim, resolved_field: Optional[ResolvedField] = None) -> List[ReasonCode]:
    """
    Validates that claim.date matches resolved_field.date if both exist (DATE_MISMATCH).
    """
    if not claim.date or not resolved_field or not resolved_field.date:
        return []

    try:
        if isinstance(claim.date, str):
            claim_dt = date.fromisoformat(claim.date[:10])
        elif isinstance(claim.date, date):
            claim_dt = claim.date
        else:
            return [ReasonCode.DATE_MISMATCH]
    except (ValueError, TypeError):
        return [ReasonCode.DATE_MISMATCH]

    if claim_dt != resolved_field.date:
        return [ReasonCode.DATE_MISMATCH]

    return []
