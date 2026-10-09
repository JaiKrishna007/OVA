from typing import List, Optional
from app.services.extraction.schemas import CandidateClaim
from app.services.validator.extraction.models import CheckDetail


def check_duplicate_claim(
    candidate: CandidateClaim,
    existing_claims: Optional[List[CandidateClaim]] = None,
) -> CheckDetail:
    """
    Check 7: Detects duplicate claims extracted within the same source record.
    - Matches identical character span offsets.
    - Matches identical field, value, and date combination.
    Hard check: Failure produces REJECTED with reason DUPLICATE_CLAIM.
    """
    if not existing_claims:
        return CheckDetail(
            name="check_duplicate_claim",
            passed=True,
            detail="No duplicate claims detected.",
            reason_code=None,
            is_hard_check=True,
        )

    cand_field = candidate.field.strip().lower()
    cand_val_str = str(candidate.value).strip().lower()
    cand_date = str(candidate.date).strip() if candidate.date else None
    cand_span = (candidate.span.start, candidate.span.end)

    for prev in existing_claims:
        prev_span = (prev.span.start, prev.span.end)
        prev_field = prev.field.strip().lower()
        prev_val_str = str(prev.value).strip().lower()
        prev_date = str(prev.date).strip() if prev.date else None

        # 1. Exact span collision for the same field
        if cand_span == prev_span and cand_field == prev_field:
            return CheckDetail(
                name="check_duplicate_claim",
                passed=False,
                detail=f"Duplicate claim: exact span [{cand_span[0]}:{cand_span[1]}] already claimed for field '{cand_field}'.",
                reason_code="DUPLICATE_CLAIM",
                is_hard_check=True,
            )

        # 2. Identical field, value, and date within the same document
        if cand_field == prev_field and cand_val_str == prev_val_str and cand_date == prev_date:
            return CheckDetail(
                name="check_duplicate_claim",
                passed=False,
                detail=f"Duplicate claim: field '{cand_field}' with value '{candidate.value}' already registered for this record.",
                reason_code="DUPLICATE_CLAIM",
                is_hard_check=True,
            )

    return CheckDetail(
        name="check_duplicate_claim",
        passed=True,
        detail="Claim is unique within record.",
        reason_code=None,
        is_hard_check=True,
    )
