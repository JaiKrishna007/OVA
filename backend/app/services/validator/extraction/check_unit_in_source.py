import re
from typing import Optional
from app.services.extraction.schemas import CandidateClaim
from app.services.extraction.normalizer import get_normalizer
from app.services.validator.extraction.models import CheckDetail


def check_unit_in_source(candidate: CandidateClaim, source_text: str) -> CheckDetail:
    """
    Check 3: The unit occurs in the source text, and unit consistency is validated.
    - If unit does not exist in source text: hard failure -> REJECTED (UNIT_NOT_IN_SOURCE).
    - If unit is incompatible with canonical field requirements: soft failure -> FLAGGED (UNIT_AMBIGUOUS).
    """
    if not candidate.unit:
        # Check if field strictly demands a unit
        normalizer = get_normalizer()
        field_cfg = normalizer.config.get("fields", {}).get(candidate.field.lower())
        if field_cfg and field_cfg.get("canonical_unit"):
            # Unit missing for quantitative lab
            return CheckDetail(
                name="check_unit_in_source",
                passed=False,
                detail=f"Field '{candidate.field}' typically requires unit '{field_cfg['canonical_unit']}' but none provided.",
                reason_code="UNIT_MISSING",
                is_hard_check=False,
            )
        return CheckDetail(
            name="check_unit_in_source",
            passed=True,
            detail="No unit claimed or required.",
            reason_code=None,
            is_hard_check=True,
        )

    clean_unit = candidate.unit.strip()

    # 1. Verify unit appears in source text (case-insensitive)
    escaped_unit = re.escape(clean_unit)
    if not re.search(escaped_unit, source_text, re.IGNORECASE):
        return CheckDetail(
            name="check_unit_in_source",
            passed=False,
            detail=f"Claimed unit '{clean_unit}' does not occur anywhere in the source document.",
            reason_code="UNIT_NOT_IN_SOURCE",
            is_hard_check=True,
        )

    # 2. Check canonical compatibility via Normalizer
    normalizer = get_normalizer()
    _, reason_codes = normalizer.normalize_unit(candidate.field, clean_unit)
    if "UNIT_AMBIGUOUS" in reason_codes:
        return CheckDetail(
            name="check_unit_in_source",
            passed=False,
            detail=f"Unit '{clean_unit}' differs from canonical standard for field '{candidate.field}'. Value preserved without silent conversion.",
            reason_code="UNIT_AMBIGUOUS",
            is_hard_check=False,  # Soft check: triggers FLAGGED
        )

    return CheckDetail(
        name="check_unit_in_source",
        passed=True,
        detail=f"Unit '{clean_unit}' confirmed in source text and matches canonical specification.",
        reason_code=None,
        is_hard_check=True,
    )
