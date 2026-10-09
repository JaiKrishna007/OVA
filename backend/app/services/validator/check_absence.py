import re
from typing import List, Dict, Any
from app.schemas.claims import Claim, ReasonCode, ClaimType, Polarity

ABSENCE_PHRASES = re.compile(
    r"(?i)\b(?:not\s+documented|not\s+on\s+file|missing|no\s+record|not\s+recorded|not\s+performed|absent|unrecorded|no\b.*?\bon\s+file)\b"
)
POSITIVE_AFFIRMATION = re.compile(
    r"(?i)\b(?:normal|performed|positive|robust|confirmed\s+normal|within\s+normal|intact|successful)\b"
)


def check_absence_ref(claim: Claim, missing_items: List[Dict[str, Any]]) -> List[ReasonCode]:
    """
    Validates ABSENCE claims:
    - An ABSENCE claim is only permissible if backed by an active Missing Data Detector item.
    - Polarity must strictly be ABSENT.
    - Display text must explicitly state missing/undocumented status and not assert positive normal findings.
    - If the item actually exists in records or is not detected by the Missing Data Detector,
      it must be BLOCKED with ABSENCE_UNSUPPORTED.
    """
    if claim.type != ClaimType.ABSENCE:
        return []

    reasons: List[ReasonCode] = []

    # Polarity check: ABSENCE claims cannot have polarity=present
    if claim.polarity != Polarity.ABSENT:
        reasons.append(ReasonCode.POLARITY_MISMATCH)

    if not missing_items:
        reasons.append(ReasonCode.ABSENCE_UNSUPPORTED)
        return reasons

    # Verify matching missing item by rule_id or item name
    matched = False
    for item in missing_items:
        rule_id = item.get("rule_id")
        item_name = item.get("item", "").lower()

        if claim.absence_rule_id and claim.absence_rule_id == rule_id:
            matched = True
            break
        if item_name and (item_name in claim.display_text.lower() or (claim.value and item_name in str(claim.value).lower())):
            matched = True
            break

    if not matched:
        reasons.append(ReasonCode.ABSENCE_UNSUPPORTED)

    # Display text check: must use absence phrasing and not assert presence/normal results
    text = claim.display_text or ""
    if not ABSENCE_PHRASES.search(text) or POSITIVE_AFFIRMATION.search(text):
        reasons.append(ReasonCode.ABSENCE_UNSUPPORTED)

    return reasons
