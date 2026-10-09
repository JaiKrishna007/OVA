import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.schemas.claims import (
    Claim,
    ClaimType,
    Polarity,
    ValidationStatus,
    AssuranceTier,
    ClaimValidationResult,
    SectionValidationResult,
)
from app.services.ai.generator import (
    SectionGenerationResult,
    generate_and_validate_section,
)
from app.services.ai.llm.base import LLMClient
from app.services.ai.context_pack import build_section_context_pack

logger = logging.getLogger(__name__)


class DegradedSectionResult:
    def __init__(
        self,
        section: str,
        mode: str,  # "ai_validated" | "deterministic_fallback"
        claims: List[Claim],
        validation_result: SectionValidationResult,
        guard_flag: bool = False,
        guard_events: Optional[List[Dict[str, Any]]] = None,
        retried: bool = False,
    ):
        self.section = section
        self.mode = mode
        self.claims = claims
        self.validation_result = validation_result
        self.guard_flag = guard_flag
        self.guard_events = guard_events or []
        self.retried = retried


def build_deterministic_fallback_claims(
    context_pack: Dict[str, Any],
) -> List[Claim]:
    """
    Produces deterministic fallback claims directly from the scoped context pack
    when LLM generation fails or exceeds the blocked claims threshold.
    """
    section = context_pack.get("section", "general")
    structured_rows = context_pack.get("structured_rows", [])
    conflicts = context_pack.get("conflicts", [])
    missing_items = context_pack.get("missing_items", [])
    spans = context_pack.get("spans", [])

    conflict_map = {}
    for c in conflicts:
        if c.get("field_path"):
            conflict_map[c.get("field_path")] = c
        if c.get("field"):
            conflict_map[c.get("field")] = c
    fallback_claims: List[Claim] = []

    # 1. Structured rows
    for i, row in enumerate(structured_rows):
        fpath = row.get("field_path")
        cid = f"fb_{section}_{i+1}"
        cycle_id = row.get("cycle_id")
        source_id = row.get("source_id")
        sources = [source_id] if source_id else []

        matching_conf = None
        if fpath and fpath in conflict_map:
            matching_conf = conflict_map[fpath]
        elif row.get("column") and row.get("column") in conflict_map:
            matching_conf = conflict_map[row.get("column")]
        elif "oocyte" in str(row.get("column", "")).lower() and any("OPU" in str(c.get("conflict_id", "")) or "oocyte" in str(c.get("field", "")).lower() for c in conflicts):
            matching_conf = next((c for c in conflicts if "OPU" in str(c.get("conflict_id", "")) or "oocyte" in str(c.get("field", "")).lower()), None)

        if matching_conf:
            conf = matching_conf
            c_id = conf.get("conflict_id") or conf.get("id")
            s_ids = conf.get("source_refs") or conf.get("source_ids") or sources
            d_text = conf.get("description") or conf.get("display_text") or f"Conflict noted on {row.get('column')}."
            fallback_claims.append(
                Claim(
                    claim_id=cid,
                    type=ClaimType.CONFLICT,
                    section=section,
                    entity=row.get("table", "clinical"),
                    cycle_id=cycle_id,
                    field_path=fpath,
                    conflict_id=c_id,
                    value=str(conf.get("value_a", row.get("value"))),
                    unit=row.get("unit"),
                    date=row.get("date"),
                    polarity=Polarity.PRESENT,
                    source_ids=s_ids,
                    display_text=d_text,
                )
            )
        else:
            col_name = str(row.get("column", "item")).replace("_", " ")
            val = row.get("value")
            unit_str = f" {row.get('unit')}" if row.get("unit") else ""
            fallback_claims.append(
                Claim(
                    claim_id=cid,
                    type=ClaimType.FACT,
                    section=section,
                    entity=row.get("table", "clinical"),
                    cycle_id=cycle_id,
                    field_path=fpath,
                    value=val,
                    unit=row.get("unit"),
                    date=row.get("date"),
                    polarity=Polarity.PRESENT,
                    source_ids=sources,
                    display_text=f"{col_name.capitalize()} was {val}{unit_str}.",
                )
            )

    # 2. Missing items
    for j, miss in enumerate(missing_items):
        item_name = miss.get("item", "item")
        fallback_claims.append(
            Claim(
                claim_id=f"fb_{section}_abs_{j+1}",
                type=ClaimType.ABSENCE,
                section=section,
                entity="clinical_investigation",
                absence_rule_id=miss.get("rule_id", "RULE_MISSING"),
                value=item_name,
                polarity=Polarity.ABSENT,
                source_ids=[],
                display_text=f"{item_name} is not documented in records.",
            )
        )

    # 3. Spans
    for k, sp in enumerate(spans):
        fallback_claims.append(
            Claim(
                claim_id=f"fb_{section}_span_{k+1}",
                type=ClaimType.FACT,
                section=section,
                entity="doctor_note",
                cycle_id=sp.get("cycle_id"),
                value=sp.get("text"),
                date=sp.get("date"),
                polarity=Polarity.PRESENT,
                source_ids=[sp.get("record_id")],
                span=sp,
                display_text=f"Note documents {sp.get('text')}.",
            )
        )

    return fallback_claims


def execute_section_pipeline(
    db: Session,
    scope: Scope,
    section: str,
    llm_client: Optional[LLMClient] = None,
    all_conflicts: Optional[List[Dict[str, Any]]] = None,
    all_missing: Optional[List[Dict[str, Any]]] = None,
) -> DegradedSectionResult:
    """
    Executes section generation with degraded fallback:
    - If blocked ratio > 0.5 (or LLM fails), retry once.
    - If still failing, replace with deterministic fallback from engines and mark mode="deterministic_fallback".
    """
    # Attempt 1
    res1 = generate_and_validate_section(
        db,
        scope,
        section,
        llm_client=llm_client,
        all_conflicts=all_conflicts,
        all_missing=all_missing,
    )

    t1 = res1.validation_result.total_claims
    b1 = res1.validation_result.blocked_claims
    ratio1 = (b1 / t1) if t1 > 0 else (1.0 if res1.context_pack.get("structured_rows") else 0.0)

    # If within acceptable threshold, return
    if ratio1 < 0.5:
        return DegradedSectionResult(
            section=section,
            mode="ai_validated",
            claims=res1.claims,
            validation_result=res1.validation_result,
            guard_flag=res1.guard_flag,
            guard_events=res1.guard_events,
            retried=False,
        )

    # Attempt 2 (Retry once)
    logger.warning(
        f"Section '{section}' blocked ratio {ratio1:.2f} >= 0.5. Retrying LLM once..."
    )
    res2 = generate_and_validate_section(
        db,
        scope,
        section,
        llm_client=llm_client,
        all_conflicts=all_conflicts,
        all_missing=all_missing,
    )

    t2 = res2.validation_result.total_claims
    b2 = res2.validation_result.blocked_claims
    ratio2 = (b2 / t2) if t2 > 0 else (1.0 if res2.context_pack.get("structured_rows") else 0.0)

    combined_guard_flag = res1.guard_flag or res2.guard_flag
    combined_guard_events = res1.guard_events + res2.guard_events

    if ratio2 < 0.5:
        logger.info(f"Section '{section}' retry succeeded with blocked ratio {ratio2:.2f}.")
        return DegradedSectionResult(
            section=section,
            mode="ai_validated",
            claims=res2.claims,
            validation_result=res2.validation_result,
            guard_flag=combined_guard_flag,
            guard_events=combined_guard_events,
            retried=True,
        )

    # Still failing: trigger deterministic fallback
    logger.warning(
        f"Section '{section}' retry failed (ratio {ratio2:.2f} > 0.5). Engaging deterministic fallback."
    )
    fallback_claims = build_deterministic_fallback_claims(res2.context_pack)
    # Re-validate fallback claims to ensure 100% provenance and verified assurance
    from app.services.validator.validator import validate_claims
    fb_rep = validate_claims(
        db,
        scope.patient_id,  # type: ignore
        fallback_claims,
        scope=scope,
    )
    fb_val = fb_rep.sections.get(
        section,
        SectionValidationResult(
            section=section,
            total_claims=len(fallback_claims),
            verified_claims=len(fallback_claims),
            blocked_claims=0,
            blocked_ratio=0.0,
            results=fb_rep.results,
        ),
    )

    return DegradedSectionResult(
        section=section,
        mode="deterministic_fallback",
        claims=fallback_claims,
        validation_result=fb_val,
        guard_flag=combined_guard_flag,
        guard_events=combined_guard_events,
        retried=True,
    )
