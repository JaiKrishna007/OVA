import re
from typing import List, Optional
from app.schemas.claims import Claim, ReasonCode, Polarity
from app.services.validator.resolver import ResolvedField


def check_polarity(claim: Claim, resolved_field: Optional[ResolvedField] = None) -> List[ReasonCode]:
    """
    Validates polarity alignment:
    - If claim says polarity="absent" but a positive/confirmed DB event exists (e.g. OHSS present).
    - If display_text contains explicit negation ('no OHSS', 'negative', 'absent') while DB entity is present.
    - If claim is of type ABSENCE, polarity must be ABSENT.
    """
    if resolved_field is None:
        if claim.type.value == "ABSENCE" and claim.polarity != Polarity.ABSENT:
            return [ReasonCode.POLARITY_MISMATCH]
        return []

    # Case 1: Polarity is explicitly marked absent, but DB row has a non-null, affirmative clinical record
    if claim.polarity == Polarity.ABSENT:
        if resolved_field.value is not None:
            # If DB row is an adverse event, a positive investigation, etc.
            if resolved_field.table in ("adverse_events", "treatment_events", "oocyte_retrievals"):
                return [ReasonCode.POLARITY_MISMATCH]

    # Case 2: Display text contains negative assertion when DB row confirms presence
    if resolved_field.table == "adverse_events" and resolved_field.value is not None:
        negation_match = re.search(r"\b(?:no|denies|negative for|absent|without)\s+([a-zA-Z]+)", claim.display_text, re.IGNORECASE)
        if negation_match:
            negated_word = negation_match.group(1).lower()
            if negated_word in str(resolved_field.value).lower() or negated_word in str(resolved_field.row.kind).lower():
                return [ReasonCode.POLARITY_MISMATCH]

    return []
