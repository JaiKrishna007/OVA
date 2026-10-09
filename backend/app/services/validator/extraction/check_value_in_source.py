import re
from typing import Any
from app.services.extraction.schemas import CandidateClaim
from app.services.validator.extraction.models import CheckDetail


def check_value_in_source(candidate: CandidateClaim, source_text: str) -> CheckDetail:
    """
    Check 2: The numeric or textual value occurs in the source text.
    Hard check: Failure produces REJECTED with reason VALUE_NOT_IN_SOURCE.
    """
    val = candidate.value
    if val is None:
        return CheckDetail(
            name="check_value_in_source",
            passed=False,
            detail="Candidate claim has null value.",
            reason_code="VALUE_NOT_IN_SOURCE",
            is_hard_check=True,
        )

    # String representation check
    str_val = str(val).strip()
    if str_val in source_text:
        return CheckDetail(
            name="check_value_in_source",
            passed=True,
            detail=f"Value '{str_val}' found in source text.",
            reason_code=None,
            is_hard_check=True,
        )

    # If numeric, check float / int representations
    if isinstance(val, (int, float)):
        # Try matching float patterns (e.g. 2.4 vs 2.40, int vs float)
        num_patterns = [
            rf"\b{val}\b",
            rf"\b{int(val)}\b" if isinstance(val, float) and val.is_integer() else None,
            rf"\b{float(val):.1f}\b",
            rf"\b{float(val):.2f}\b",
        ]
        for pat in filter(None, num_patterns):
            if re.search(pat, source_text):
                return CheckDetail(
                    name="check_value_in_source",
                    passed=True,
                    detail=f"Numeric value '{val}' matched in source text.",
                    reason_code=None,
                    is_hard_check=True,
                )

    # Value not found anywhere in document
    return CheckDetail(
        name="check_value_in_source",
        passed=False,
        detail=f"Claimed value '{val}' was not found anywhere in the source document.",
        reason_code="VALUE_NOT_IN_SOURCE",
        is_hard_check=True,
    )
