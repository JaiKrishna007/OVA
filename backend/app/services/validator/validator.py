from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.schemas.claims import (
    Claim,
    ClaimType,
    ValidationStatus,
    AssuranceTier,
    ReasonCode,
    ClaimValidationResult,
    SectionValidationResult,
    ValidationReport,
)
from app.services.engines.conflicts import detect_conflicts
from app.services.engines.missing import detect_missing_data

from app.services.validator.resolver import resolve_field_path, ResolvedField
from app.services.validator.check_source import check_source_exists
from app.services.validator.check_scope import check_scope
from app.services.validator.check_date import check_date_match
from app.services.validator.check_value import check_value_match
from app.services.validator.check_text_numbers import check_display_text_numbers
from app.services.validator.check_medication import check_medication_match
from app.services.validator.check_polarity import check_polarity
from app.services.validator.check_severity import check_severity_grade
from app.services.validator.check_span import check_span
from app.services.validator.check_conflict import check_active_conflict
from app.services.validator.check_absence import check_absence_ref
from app.services.validator.check_policy import check_policy_filter


def validate_claim(
    db: Session,
    target_patient_id: str,
    claim: Claim,
    active_conflicts: Optional[List[Dict[str, Any]]] = None,
    missing_items: Optional[List[Dict[str, Any]]] = None,
) -> ClaimValidationResult:
    """
    Executes programmatic validation across all 12 checks on a single claim.
    No LLM calls are made. Produces a deterministic verdict and assurance tier.
    """
    if active_conflicts is None:
        active_conflicts = detect_conflicts(db, Scope(user=None, patient_id=target_patient_id))  # type: ignore

    if missing_items is None:
        missing_items = detect_missing_data(db, Scope(user=None, patient_id=target_patient_id))  # type: ignore

    reasons: List[ReasonCode] = []

    # 1. Clinical policy filter
    reasons.extend(check_policy_filter(claim))

    # 2. Source existence and patient scope for sources
    reasons.extend(check_source_exists(db, target_patient_id, claim))

    # 3. Grounded numerals in display_text
    reasons.extend(check_display_text_numbers(claim, active_conflicts))

    # 4. Note-supported text span check
    if claim.span:
        reasons.extend(check_span(db, target_patient_id, claim))

    # 5. Active conflict check
    reasons.extend(check_active_conflict(claim, active_conflicts or []))

    # 6. Absence reference check
    if claim.type == ClaimType.ABSENCE:
        reasons.extend(check_absence_ref(claim, missing_items or []))

    # 7. Field path resolution & structured entity checks
    resolved_field: Optional[ResolvedField] = None
    if claim.field_path:
        resolved_field = resolve_field_path(db, claim.field_path)
        if not resolved_field:
            reasons.append(ReasonCode.FIELD_PATH_INVALID)
        else:
            reasons.extend(check_scope(target_patient_id, claim, resolved_field))
            reasons.extend(check_date_match(claim, resolved_field))
            reasons.extend(check_value_match(claim, resolved_field))
            reasons.extend(check_medication_match(claim, resolved_field))
            reasons.extend(check_polarity(claim, resolved_field))
            reasons.extend(check_severity_grade(claim, resolved_field))
    else:
        # Structured FACT claim without span and without field path cannot resolve
        if claim.type == ClaimType.FACT and not claim.span:
            reasons.append(ReasonCode.FIELD_PATH_INVALID)

    # De-duplicate reason codes preserving order
    unique_reasons: List[ReasonCode] = []
    for r in reasons:
        if r not in unique_reasons:
            unique_reasons.append(r)

    # Determine verdict and assurance tier
    if unique_reasons:
        status = ValidationStatus.BLOCKED
        tier = AssuranceTier.BLOCKED
    else:
        status = ValidationStatus.VERIFIED
        if claim.span:
            tier = AssuranceTier.NOTE_SUPPORTED
        else:
            tier = AssuranceTier.STRUCTURED_VERIFIED

    return ClaimValidationResult(
        claim_id=claim.claim_id,
        status=status,
        assurance_tier=tier,
        reason_codes=unique_reasons,
        claim=claim,
    )


def validate_claims(
    db: Session,
    target_patient_id: str,
    claims: List[Claim],
    scope: Optional[Scope] = None,
) -> ValidationReport:
    """
    Validates a list of claims for a patient across all sections.
    Computes per-claim results, per-section blocked counts/ratios, and overall summary.
    """
    eval_scope = scope or Scope(user=None, patient_id=target_patient_id)  # type: ignore

    active_conflicts = detect_conflicts(db, eval_scope)
    missing_items = detect_missing_data(db, eval_scope)

    results: List[ClaimValidationResult] = []
    section_map: Dict[str, List[ClaimValidationResult]] = {}

    for claim in claims:
        res = validate_claim(
            db=db,
            target_patient_id=target_patient_id,
            claim=claim,
            active_conflicts=active_conflicts,
            missing_items=missing_items,
        )
        results.append(res)
        section_map.setdefault(claim.section, []).append(res)

    # Compute section breakdown
    section_results: Dict[str, SectionValidationResult] = {}
    total_blocked = 0
    total_verified = 0

    for section_name, s_results in section_map.items():
        s_total = len(s_results)
        s_blocked = sum(1 for r in s_results if r.status == ValidationStatus.BLOCKED)
        s_verified = s_total - s_blocked
        s_ratio = round(s_blocked / s_total, 4) if s_total > 0 else 0.0

        section_results[section_name] = SectionValidationResult(
            section=section_name,
            total_claims=s_total,
            verified_claims=s_verified,
            blocked_claims=s_blocked,
            blocked_ratio=s_ratio,
            results=s_results,
        )
        total_blocked += s_blocked
        total_verified += s_verified

    total_count = len(results)
    overall_ratio = round(total_blocked / total_count, 4) if total_count > 0 else 0.0

    return ValidationReport(
        patient_id=target_patient_id,
        total_claims=total_count,
        verified_claims=total_verified,
        blocked_claims=total_blocked,
        blocked_ratio=overall_ratio,
        sections=section_results,
        results=results,
    )
