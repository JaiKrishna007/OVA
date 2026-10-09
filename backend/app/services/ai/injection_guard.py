import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Patterns that indicate prompt injection, role-play escape, or imperative instruction overrides
INJECTION_PATTERNS = [
    re.compile(r"(?i)\b(?:system\s+(?:note|override)|admin\s+note|developer\s+mode)\s*:", re.IGNORECASE),
    re.compile(r"(?i)\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts|rules|commands)\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:state\s+that\s+the\s+patient|output\s+(?:only\s+)?the\s+following|say\s+that)\b", re.IGNORECASE),
    re.compile(r"(?i)<\/?(?:system|instruction|prompt|guard)>", re.IGNORECASE),
    re.compile(r"(?i)\b(?:jailbreak|bypass\s+(?:safety|filter|guard|policy|rules))\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:new\s+(?:system\s+)?instruction|system\s+prompt)\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:disregard|override|bypass)\s+(?:safety|rules|constraints|instructions)\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:do\s+not\s+follow|stop\s+following)\s+(?:system|safety|previous)\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:DAN\s+mode|unrestricted\s+mode)\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:reveal|leak|print|show)\s+(?:the\s+)?(?:system\s+prompt|developer\s+instructions)\b", re.IGNORECASE),
]


def sanitize_string(
    text: str,
    context_label: str = "field",
) -> Tuple[str, bool, List[Dict[str, Any]]]:
    """
    Sanitizes any string value against prompt injection patterns.
    """
    if not text or not isinstance(text, str):
        return text, False, []

    detected_events: List[Dict[str, Any]] = []
    neutralized_text = text

    for pattern in INJECTION_PATTERNS:
        matches = list(pattern.finditer(neutralized_text))
        if matches:
            for m in matches:
                matched_str = m.group(0)
                detected_events.append({
                    "context": context_label,
                    "matched_pattern": pattern.pattern,
                    "snippet": matched_str,
                })
                logger.warning(
                    f"Prompt injection pattern detected in {context_label}: '{matched_str}'. Neutralizing."
                )
            neutralized_text = pattern.sub("[POTENTIAL_INJECTION_NEUTRALIZED]", neutralized_text)

    has_flag = len(detected_events) > 0
    return neutralized_text, has_flag, detected_events


def guard_note_text(
    record_id: str,
    text: str,
    origin_org: str = "",
) -> Tuple[str, bool, List[Dict[str, Any]]]:
    """
    Sanitizes raw clinical note text:
    - Neutralizes suspected instruction-like injection patterns.
    - Wraps note content in strict untrusted data boundaries.
    - Returns (guarded_text, has_injection_flag, detected_events).
    """
    if not text:
        return "", False, []

    neutralized_text, has_flag, detected_events = sanitize_string(text, context_label=f"record:{record_id}")
    clean_origin, origin_flag, origin_events = sanitize_string(origin_org, context_label=f"record:{record_id}:origin")
    if origin_flag:
        has_flag = True
        detected_events.extend(origin_events)

    # Wrap in strict untrusted data boundaries
    guarded_text = (
        f'<untrusted_clinical_data record_id="{record_id}" origin="{clean_origin}">\n'
        f'{neutralized_text.strip()}\n'
        f'</untrusted_clinical_data>'
    )

    return guarded_text, has_flag, detected_events


def guard_context_pack(pack: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, List[Dict[str, Any]]]:
    """
    Recursively scans the entire context pack (notes, diagnoses, authors, organizations,
    investigation results, management notes) against injection patterns, wrapping note contents
    in untrusted boundaries and setting the guard flag if any injection attempt is found.
    """
    all_events: List[Dict[str, Any]] = []
    flag_raised = False

    def _recursive_sanitize(obj: Any, path: str = "") -> Any:
        nonlocal flag_raised, all_events
        if isinstance(obj, str):
            clean_str, flagged, events = sanitize_string(obj, context_label=path or "field")
            if flagged:
                flag_raised = True
                all_events.extend(events)
            return clean_str
        elif isinstance(obj, dict):
            new_dict = {}
            is_note = "content_text" in obj and ("record_id" in obj or "id" in obj)
            for k, v in obj.items():
                child_path = f"{path}.{k}" if path else k
                if is_note and k == "content_text":
                    rec_id = obj.get("record_id") or obj.get("id") or "UNKNOWN"
                    origin = obj.get("origin_org", "")
                    g_text, flagged, events = guard_note_text(rec_id, v, origin)
                    if flagged:
                        flag_raised = True
                        all_events.extend(events)
                    new_dict[k] = g_text
                else:
                    new_dict[k] = _recursive_sanitize(v, child_path)
            return new_dict
        elif isinstance(obj, list):
            return [_recursive_sanitize(item, f"{path}[{i}]") for i, item in enumerate(obj)]
        return obj

    guarded_pack = _recursive_sanitize(pack)
    return guarded_pack, flag_raised, all_events
