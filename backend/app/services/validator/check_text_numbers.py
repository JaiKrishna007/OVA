import re
from typing import List, Set, Any
from app.schemas.claims import Claim, ReasonCode


def _extract_numbers(text: str) -> Set[str]:
    """Extracts all string representations of numeric tokens (integers and decimals)."""
    if not text:
        return set()
    tokens = re.findall(r"\b\d+(?:\.\d+)?\b", str(text))
    result = set()
    for tok in tokens:
        result.add(tok)
        # Normalize leading zeros and float equivalents
        try:
            if "." in tok:
                f_val = float(tok)
                result.add(str(f_val))
                if f_val.is_integer():
                    result.add(str(int(f_val)))
            else:
                i_val = int(tok)
                result.add(str(i_val))
        except ValueError:
            pass
    return result


def check_display_text_numbers(
    claim: Claim,
    active_conflicts: Optional[List[Dict[str, Any]]] = None,
) -> List[ReasonCode]:
    """
    Validates that every numeral and date number mentioned in display_text
    is grounded in the claim's value, date, cycle_id, field_path, or known context.
    Prevents hallucinated numbers in display_text.
    """
    if not claim.display_text:
        return []

    text_numbers = _extract_numbers(claim.display_text)
    if not text_numbers:
        return []

    # Build allowed context numbers
    allowed: Set[str] = set()

    # 1. From value
    if claim.value is not None:
        allowed.update(_extract_numbers(str(claim.value)))

    # 2. From date
    if claim.date:
        allowed.update(_extract_numbers(claim.date))

    # 3. From cycle_id
    if claim.cycle_id:
        allowed.update(_extract_numbers(claim.cycle_id))

    # 4. From field_path
    if claim.field_path:
        allowed.update(_extract_numbers(claim.field_path))

    # 5. From unit
    if claim.unit:
        allowed.update(_extract_numbers(claim.unit))

    # 6. From entity / section
    allowed.update(_extract_numbers(claim.entity))
    allowed.update(_extract_numbers(claim.section))

    # 7. For CONFLICT claims, include values from active conflict
    if active_conflicts:
        for conf in active_conflicts:
            cid = conf.get("conflict_id") or conf.get("id")
            cfield = conf.get("field")
            is_match = False
            if claim.conflict_id and (claim.conflict_id == cid or claim.conflict_id == conf.get("id")):
                is_match = True
            elif claim.field_path and (conf.get("field_path") == claim.field_path or (cfield and cfield in claim.field_path)):
                is_match = True
            elif claim.entity and "oocyte" in claim.entity.lower() and ("OPU" in str(cid) or "oocyte" in str(cfield).lower()):
                is_match = True

            if is_match:
                allowed.update(_extract_numbers(str(conf.get("value_a", ""))))
                allowed.update(_extract_numbers(str(conf.get("value_b", ""))))
                allowed.update(_extract_numbers(str(conf.get("description", ""))))
                allowed.update(_extract_numbers(str(conf.get("display_text", ""))))

    # Check for ungrounded numbers in display text
    for num in text_numbers:
        if num not in allowed:
            # If it's an integer, check if its int equivalent is in allowed
            try:
                if str(int(num)) in allowed:
                    continue
            except ValueError:
                pass
            return [ReasonCode.TEXT_NUMBER_MISMATCH]

    return []
