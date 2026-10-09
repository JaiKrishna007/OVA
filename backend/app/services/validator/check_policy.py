import json
import re
from pathlib import Path
from typing import List, Dict, Any
from app.schemas.claims import Claim, ReasonCode

CONFIG_PATH = Path(__file__).parent / "policy_rules.json"


def _load_policy_rules() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_RULES = _load_policy_rules()
_COMPILED_PATTERNS = []

# Compile regex patterns from config
for group in ["dosing_advice_patterns", "treatment_recommendation_patterns", "new_diagnosis_patterns"]:
    for pat in _RULES.get(group, []):
        _COMPILED_PATTERNS.append(re.compile(pat))

# Compile imperative word boundaries
_IMPERATIVE_WORDS = [
    re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
    for w in _RULES.get("imperative_keywords", [])
]


def check_policy_filter(claim: Claim) -> List[ReasonCode]:
    """
    Evaluates the claim display_text against clinical policy constraints:
    - Never recommend dosing, protocols, diagnoses, or treatment.
    - No imperative clinical language ("should", "recommend", "consider starting", "increase").
    - Blocks with POLICY_VIOLATION if any policy rule triggers.
    """
    text = claim.display_text or ""
    if not text:
        return []

    # Check compiled regex patterns
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return [ReasonCode.POLICY_VIOLATION]

    # Check imperative keywords
    for word_pattern in _IMPERATIVE_WORDS:
        if word_pattern.search(text):
            return [ReasonCode.POLICY_VIOLATION]

    return []
