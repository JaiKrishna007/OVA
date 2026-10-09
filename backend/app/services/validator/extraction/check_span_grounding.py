import re
from app.services.extraction.schemas import CandidateClaim
from app.services.validator.extraction.models import CheckDetail


def check_span_grounding(candidate: CandidateClaim, source_text: str) -> CheckDetail:
    """
    Check 5: Strict span grounding verification:
    - Evidence text must not be empty (EMPTY_EVIDENCE).
    - Span boundaries must fall within document bounds (SPAN_OUT_OF_RANGE).
    - source_text[span.start:span.end] must exactly equal evidence_text (SPAN_MISMATCH).
    - The evidence slice must contain the claimed value (VALUE_NOT_IN_SPAN).
    Hard check: Failure produces REJECTED.
    """
    evidence = candidate.evidence_text
    if not evidence or not evidence.strip():
        return CheckDetail(
            name="check_span_grounding",
            passed=False,
            detail="Candidate claim has empty or whitespace evidence text.",
            reason_code="EMPTY_EVIDENCE",
            is_hard_check=True,
        )

    span = candidate.span
    text_len = len(source_text)

    # 1. Bounds check
    if span.start < 0 or span.end > text_len or span.start >= span.end:
        return CheckDetail(
            name="check_span_grounding",
            passed=False,
            detail=f"Span [{span.start}:{span.end}] is out of range for document of length {text_len}.",
            reason_code="SPAN_OUT_OF_RANGE",
            is_hard_check=True,
        )

    # 2. Exact slice match
    actual_slice = source_text[span.start:span.end]
    if actual_slice != evidence:
        return CheckDetail(
            name="check_span_grounding",
            passed=False,
            detail=f"Character span mismatch: document[{span.start}:{span.end}] = '{actual_slice}' != evidence_text '{evidence}'.",
            reason_code="SPAN_MISMATCH",
            is_hard_check=True,
        )

    # 3. Value containment in evidence slice
    val = candidate.value
    if val is not None:
        str_val = str(val).strip()
        found_in_span = False
        if str_val in evidence:
            found_in_span = True
        elif isinstance(val, (int, float)):
            # Check number patterns in evidence
            if re.search(rf"\b{val}\b", evidence) or (isinstance(val, float) and val.is_integer() and re.search(rf"\b{int(val)}\b", evidence)):
                found_in_span = True
        elif isinstance(val, str):
            if val.lower() in evidence.lower():
                found_in_span = True

        if not found_in_span:
            return CheckDetail(
                name="check_span_grounding",
                passed=False,
                detail=f"Evidence text '{evidence}' does not contain the claimed value '{val}'.",
                reason_code="VALUE_NOT_IN_SPAN",
                is_hard_check=True,
            )

    return CheckDetail(
        name="check_span_grounding",
        passed=True,
        detail=f"Span [{span.start}:{span.end}] matches source text exactly and contains value '{val}'.",
        reason_code=None,
        is_hard_check=True,
    )
