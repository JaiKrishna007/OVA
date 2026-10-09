from typing import List, Optional
from app.models.enums import ClaimValidationStatus
from app.services.extraction.schemas import CandidateClaim
from app.services.validator.extraction.models import CheckDetail, ValidationResult
from app.services.validator.extraction.check_known_field import check_known_field
from app.services.validator.extraction.check_value_in_source import check_value_in_source
from app.services.validator.extraction.check_unit_in_source import check_unit_in_source
from app.services.validator.extraction.check_date_in_source import check_date_in_source
from app.services.validator.extraction.check_span_grounding import check_span_grounding
from app.services.validator.extraction.check_context_attachment import check_context_attachment
from app.services.validator.extraction.check_duplicate import check_duplicate_claim


class ExtractionValidator:
    """
    Deterministic programmatic validator for candidate clinical claims.
    Evaluates 7 distinct checks with zero LLM calls:
    1. check_known_field: Canonical field recognition (FIELD_UNKNOWN).
    2. check_value_in_source: Occurrence of value in source text (VALUE_NOT_IN_SOURCE).
    3. check_unit_in_source: Unit occurrence (UNIT_NOT_IN_SOURCE) and consistency (UNIT_AMBIGUOUS).
    4. check_date_in_source: Date occurrence and calendar equivalence (DATE_NOT_IN_SOURCE).
    5. check_span_grounding: Exact substring slice grounding (SPAN_MISMATCH, SPAN_OUT_OF_RANGE, EMPTY_EVIDENCE).
    6. check_context_attachment: Context window field association (CONTEXT_MISMATCH).
    7. check_duplicate_claim: Duplicate detection within record (DUPLICATE_CLAIM).

    Verdict logic:
    - Any failed hard check -> REJECTED
    - Soft checks (UNIT_AMBIGUOUS, DATE_LOW_CONFIDENCE) -> FLAGGED
    - All passed -> VERIFIED
    """

    @classmethod
    def validate(
        cls,
        candidate: CandidateClaim,
        source_text: str,
        existing_claims: Optional[List[CandidateClaim]] = None,
        context_window_chars: int = 100,
    ) -> ValidationResult:
        checks: List[CheckDetail] = []
        reason_codes: List[str] = []

        # 1. Field recognition
        res_field = check_known_field(candidate)
        checks.append(res_field)
        if not res_field.passed and res_field.reason_code:
            reason_codes.append(res_field.reason_code)

        # 2. Value presence in source
        res_val = check_value_in_source(candidate, source_text)
        checks.append(res_val)
        if not res_val.passed and res_val.reason_code:
            reason_codes.append(res_val.reason_code)

        # 3. Unit presence and canonical compatibility
        res_unit = check_unit_in_source(candidate, source_text)
        checks.append(res_unit)
        if not res_unit.passed and res_unit.reason_code:
            reason_codes.append(res_unit.reason_code)

        # 4. Date presence and calendar equivalence
        res_date = check_date_in_source(candidate, source_text)
        checks.append(res_date)
        if not res_date.passed and res_date.reason_code:
            reason_codes.append(res_date.reason_code)

        # 5. Span grounding & exact text slice match
        res_span = check_span_grounding(candidate, source_text)
        checks.append(res_span)
        if not res_span.passed and res_span.reason_code:
            reason_codes.append(res_span.reason_code)

        # 6. Context attachment & competitor avoidance
        res_ctx = check_context_attachment(candidate, source_text, window_chars=context_window_chars)
        checks.append(res_ctx)
        if not res_ctx.passed and res_ctx.reason_code:
            reason_codes.append(res_ctx.reason_code)

        # 7. Duplicate claim detection
        res_dup = check_duplicate_claim(candidate, existing_claims)
        checks.append(res_dup)
        if not res_dup.passed and res_dup.reason_code:
            reason_codes.append(res_dup.reason_code)

        # Determine overall validation verdict
        has_hard_failure = any(not c.passed and c.is_hard_check for c in checks)
        has_soft_failure = any(not c.passed and not c.is_hard_check for c in checks)

        if has_hard_failure:
            status = ClaimValidationStatus.REJECTED
        elif has_soft_failure:
            status = ClaimValidationStatus.FLAGGED
        else:
            status = ClaimValidationStatus.VERIFIED

        return ValidationResult(
            status=status,
            checks=checks,
            reason_codes=reason_codes,
        )
