"""
Deterministic S1 Safety Filter (Kernel Prime'26, Section 16).

Enforces Non-Negotiable Safety Rule S1:
Never recommend dosing, protocols, diagnoses, or treatment.
Deterministic classifier BLOCKS recommendation-seeking questions and ALLOWS documented-fact lookups.
Ambiguous questions are blocked with a clarifying hint ("Try asking what is documented").
Rules live in backend/app/config/s1_rules.yaml.
"""

import os
import re
import yaml
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "s1_rules.yaml")
)


class S1Decision(str, Enum):
    BLOCK = "BLOCK"
    ALLOW = "ALLOW"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class S1FilterResult:
    decision: S1Decision
    status: str
    rule_id: str
    reason: str
    message: str
    hint: Optional[str] = None


# Module-level cache for compiled rule patterns
_COMPILED_RULES: Optional[Dict[str, Any]] = None


def _load_rules() -> Dict[str, Any]:
    """Loads and compiles rules from s1_rules.yaml."""
    global _COMPILED_RULES
    if _COMPILED_RULES is not None:
        return _COMPILED_RULES

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"S1 rules configuration file not found at {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    block_rules = []
    for r in raw_config.get("block_rules", []):
        compiled_patterns = [re.compile(pat) for pat in r.get("patterns", [])]
        block_rules.append(
            {
                "id": r["id"],
                "description": r.get("description", ""),
                "patterns": compiled_patterns,
            }
        )

    allow_rules = []
    for r in raw_config.get("allow_rules", []):
        compiled_patterns = [re.compile(pat) for pat in r.get("patterns", [])]
        allow_rules.append(
            {
                "id": r["id"],
                "description": r.get("description", ""),
                "patterns": compiled_patterns,
            }
        )

    _COMPILED_RULES = {
        "block_message": raw_config.get(
            "block_message",
            "I can only report what is documented in the records. I cannot provide clinical recommendations.",
        ),
        "ambiguous_hint": raw_config.get("ambiguous_hint", "Try asking what is documented"),
        "block_rules": block_rules,
        "allow_rules": allow_rules,
    }
    return _COMPILED_RULES


def reload_rules() -> None:
    """Forces reloading of the YAML config file (useful for testing)."""
    global _COMPILED_RULES
    _COMPILED_RULES = None
    _load_rules()


def evaluate_s1_safety(question: str) -> S1FilterResult:
    """
    Evaluates clinical query through deterministic S1 safety rules.
    
    Order of operations:
    1. Check recommendation-seeking / prescriptive rules -> BLOCK with status BLOCKED_S1.
    2. Check documented-fact lookup rules -> ALLOW with status ALLOWED.
    3. Neither matches -> AMBIGUOUS with status BLOCKED_S1 and clarifying hint.
    """
    rules = _load_rules()
    q_clean = question.strip()
    block_msg = rules["block_message"]
    ambiguous_hint = rules["ambiguous_hint"]

    # 1. Recommendation-seeking intent check (BLOCK)
    for rule in rules["block_rules"]:
        for pattern in rule["patterns"]:
            if pattern.search(q_clean):
                rule_id = rule["id"]
                logger.info(f"[S1_FILTER] Decision=BLOCK Rule={rule_id} Query='{q_clean}'")
                resp_msg = block_msg
                if rule_id == "S1_BLOCK_PROMPT_INJECTION":
                    resp_msg = (
                        "Unable to process question containing instruction override directives. "
                        + block_msg
                    )
                return S1FilterResult(
                    decision=S1Decision.BLOCK,
                    status="BLOCKED_S1",
                    rule_id=rule_id,
                    reason=rule["description"],
                    message=resp_msg,
                    hint=None,
                )

    # 2. Documented-fact lookup check (ALLOW)
    for rule in rules["allow_rules"]:
        for pattern in rule["patterns"]:
            if pattern.search(q_clean):
                rule_id = rule["id"]
                logger.info(f"[S1_FILTER] Decision=ALLOW Rule={rule_id} Query='{q_clean}'")
                return S1FilterResult(
                    decision=S1Decision.ALLOW,
                    status="ALLOWED",
                    rule_id=rule_id,
                    reason=rule["description"],
                    message="",
                    hint=None,
                )

    # 3. Ambiguous intent check (BLOCKED_S1 with clarifying hint)
    rule_id = "S1_AMBIGUOUS_CLARIFY"
    logger.info(f"[S1_FILTER] Decision=AMBIGUOUS Rule={rule_id} Query='{q_clean}'")
    return S1FilterResult(
        decision=S1Decision.AMBIGUOUS,
        status="BLOCKED_S1",
        rule_id=rule_id,
        reason="Ambiguous intent - no documented fact indicators found",
        message=block_msg,
        hint=ambiguous_hint,
    )
