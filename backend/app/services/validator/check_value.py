from typing import List, Optional, Any
from app.schemas.claims import Claim, ReasonCode, ClaimType
from app.services.validator.resolver import ResolvedField


def check_value_match(claim: Claim, resolved_field: Optional[ResolvedField] = None) -> List[ReasonCode]:
    """
    Validates that claim.value matches resolved_field.value:
    - If resolved_field has a value, claim.value cannot be None.
    - Exact match for integers.
    - Floating point matching within 1e-4 tolerance.
    - Case-insensitive string matching.
    - Display text must not omit or contradict string/enum values.
    """
    if resolved_field is None or resolved_field.value is None or claim.type == ClaimType.CONFLICT:
        return []

    # If database has a concrete value, claim cannot omit it (claim.value=None bypass)
    if claim.value is None:
        return [ReasonCode.VALUE_MISMATCH]

    c_val = claim.value
    db_val = resolved_field.value

    # Integer comparison
    if isinstance(db_val, int) and not isinstance(db_val, bool):
        try:
            if int(c_val) != db_val:
                return [ReasonCode.VALUE_MISMATCH]
            return []
        except (ValueError, TypeError):
            return [ReasonCode.VALUE_MISMATCH]

    # Float comparison
    if isinstance(db_val, float):
        try:
            c_float = float(c_val)
            if abs(c_float - db_val) > 1e-4:
                return [ReasonCode.VALUE_MISMATCH]
            return []
        except (ValueError, TypeError):
            return [ReasonCode.VALUE_MISMATCH]

    # String / enum comparison
    c_str = str(c_val).strip().lower()
    db_str = str(db_val).strip().lower()

    if c_str != db_str:
        return [ReasonCode.VALUE_MISMATCH]

    # Ensure display text reflects the resolved string/enum value rather than contradicting it
    if claim.display_text:
        d_lower = claim.display_text.lower()
        db_clean = db_str.replace("_", " ")
        if db_str not in d_lower and db_clean not in d_lower:
            # Allow boolean/flag conversions or number representations
            if db_str not in ("true", "false", "yes", "no"):
                return [ReasonCode.VALUE_MISMATCH]

    return []
