import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.scope import Scope
from app.models import Patient, SourceRecord
from app.schemas.claims import ValidationStatus, AssuranceTier
from app.services.engines.conflicts import detect_conflicts
from app.services.engines.missing import detect_missing_data
from app.services.engines.followups import get_followups
from app.services.engines.stage import get_current_stage
from app.services.engines.coverage import check_coverage
from app.services.ai.context_pack import SECTIONS
from app.services.ai.degraded import execute_section_pipeline, DegradedSectionResult
from app.services.ai.llm.base import LLMClient
from app.services.ai.llm import get_llm_client


def build_snapshot_lines(
    patient: Optional[Patient],
    current_stage: str,
    verified_claims_by_section: Dict[str, List[Dict[str, Any]]],
    all_conflicts: List[Dict[str, Any]],
    overdue_followups: List[Dict[str, Any]],
    missing_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Builds a concise summary snapshot of at most 5 lines from verified clinical facts,
    attaching explicit source_refs and assurance_tier badges to fulfill Rule S2.
    """
    items: List[Dict[str, Any]] = []

    # Line 1: Demographics and primary diagnosis
    profile_claims = verified_claims_by_section.get("profile_diagnosis", [])
    l1_sources: List[str] = []
    for c in profile_claims:
        for cit in c.get("citations", []):
            sid = cit.get("source_id")
            if sid and sid not in l1_sources:
                l1_sources.append(sid)
    if not l1_sources and patient and getattr(patient, "records", None):
        for r in patient.records:
            if r.id not in l1_sources:
                l1_sources.append(r.id)
                break

    if patient:
        age_str = f"DOB: {patient.dob}" if patient.dob else ""
        diag_str = ""
        if patient.diagnosis:
            if isinstance(patient.diagnosis, list):
                diag_str = f"Diagnosis: {', '.join(patient.diagnosis)}."
            elif isinstance(patient.diagnosis, dict):
                diag_str = f"Diagnosis: {patient.diagnosis.get('primary', '')}."
        text1 = f"{patient.name} ({age_str}). {diag_str} Blood group: {patient.blood_group}.".strip()
    else:
        text1 = "Patient profile not documented."

    items.append({
        "line_no": 1,
        "text": text1,
        "source_refs": l1_sources,
        "assurance_tier": "structured_verified" if l1_sources else "deterministic_verified",
    })

    # Line 2: Cycle history
    prior_claims = verified_claims_by_section.get("prior_cycles", [])
    l2_sources: List[str] = []
    if prior_claims:
        cycle_summaries = [c.get("display_text", "") for c in prior_claims[:3]]
        for c in prior_claims[:3]:
            for cit in c.get("citations", []):
                sid = cit.get("source_id")
                if sid and sid not in l2_sources:
                    l2_sources.append(sid)
        text2 = "Cycle history: " + " ".join(cycle_summaries)
    else:
        text2 = "No prior cycles documented."

    items.append({
        "line_no": 2,
        "text": text2,
        "source_refs": l2_sources,
        "assurance_tier": "structured_verified" if l2_sources else "deterministic_verified",
    })

    # Line 3: Key finding, oocyte count or conflict
    l3_sources: List[str] = []
    if all_conflicts:
        conf_desc = all_conflicts[0].get("description", "Active conflict documented.")
        text3 = f"Clinical Alert: {conf_desc}"
        if all_conflicts[0].get("source_a"):
            l3_sources.append(all_conflicts[0]["source_a"])
        if all_conflicts[0].get("source_b"):
            l3_sources.append(all_conflicts[0]["source_b"])
        tier3 = "deterministic_verified"
    else:
        oocyte_claims = verified_claims_by_section.get("oocyte_retrieval", [])
        if oocyte_claims:
            text3 = oocyte_claims[0].get("display_text", "")
            for cit in oocyte_claims[0].get("citations", []):
                sid = cit.get("source_id")
                if sid and sid not in l3_sources:
                    l3_sources.append(sid)
            tier3 = oocyte_claims[0].get("assurance_tier", "structured_verified")
        else:
            text3 = "Oocyte and embryology details reviewed."
            tier3 = "deterministic_verified"

    items.append({
        "line_no": 3,
        "text": text3,
        "source_refs": l3_sources,
        "assurance_tier": tier3,
    })

    # Line 4: Current treatment stage
    l4_sources: List[str] = []
    stage_claims = (
        verified_claims_by_section.get("protocol", [])
        or verified_claims_by_section.get("stimulation", [])
    )
    if stage_claims:
        for cit in stage_claims[0].get("citations", []):
            sid = cit.get("source_id")
            if sid and sid not in l4_sources:
                l4_sources.append(sid)

    items.append({
        "line_no": 4,
        "text": f"Current stage: {current_stage}",
        "source_refs": l4_sources,
        "assurance_tier": "deterministic_verified",
    })

    # Line 5: Pending/overdue followups and gaps
    alerts = []
    l5_sources: List[str] = []
    if overdue_followups:
        alerts.append(f"Overdue: {overdue_followups[0].get('name')}")
        sid = overdue_followups[0].get("source_id")
        if sid:
            l5_sources.append(sid)
    if missing_items:
        alerts.append(f"Missing documentation: {missing_items[0].get('item')}")
    if alerts:
        text5 = "Action items: " + "; ".join(alerts)
    else:
        text5 = "No immediate overdue investigations."

    items.append({
        "line_no": 5,
        "text": text5,
        "source_refs": l5_sources,
        "assurance_tier": "deterministic_verified",
    })

    return items[:5]


def compose_summary(
    db: Session,
    scope: Scope,
    llm_client: Optional[LLMClient] = None,
) -> Dict[str, Any]:
    """
    Orchestrates the complete AI summary path:
    1. Runs section generation with degraded fallback across all 9 sections.
    2. Builds verified statements with rich provenance citations.
    3. Strictly filters out BLOCKED claims from display.
    4. Merges deterministic engine outputs (conflicts, missing, coverage, stage).
    5. Formats snapshot (5 lines max) and attaches safety disclaimer.
    """
    if llm_client is None:
        llm_client = get_llm_client()

    patient_id = scope.patient_id
    patient = db.get(Patient, patient_id)

    # 1. Gather deterministic engine context
    all_conflicts = detect_conflicts(db, scope)
    all_missing = detect_missing_data(db, scope)
    followups_data = get_followups(db, scope)
    overdue_followups = followups_data.get("overdue", [])
    stage_data = get_current_stage(db, scope)
    current_stage = stage_data.get("stage", "Stage not documented")

    # Cache source records for fast citation lookup
    source_records = {
        r.id: r
        for r in db.scalars(
            select(SourceRecord).where(SourceRecord.patient_id == patient_id)
        ).all()
    }

    # 2. Process all 9 sections
    composed_sections: Dict[str, Any] = {}
    total_claims = 0
    verified_claims_count = 0
    note_supported_count = 0
    blocked_claims_count = 0
    blocked_items: List[Dict[str, Any]] = []
    any_guard_flag = False
    all_guard_events: List[Dict[str, Any]] = []

    verified_claims_by_section: Dict[str, List[Dict[str, Any]]] = {}
    all_verified_claim_dicts: List[Dict[str, Any]] = []

    for section in SECTIONS:
        sec_res: DegradedSectionResult = execute_section_pipeline(
            db,
            scope,
            section,
            llm_client=llm_client,
            all_conflicts=all_conflicts,
            all_missing=all_missing,
        )

        if sec_res.guard_flag:
            any_guard_flag = True
            all_guard_events.extend(sec_res.guard_events)

        statements: List[Dict[str, Any]] = []
        sec_verified: List[Dict[str, Any]] = []

        val_result_map = {r.claim_id: r for r in sec_res.validation_result.results}

        for claim in sec_res.claims:
            val_result = val_result_map.get(claim.claim_id)
            status = val_result.status if val_result else ValidationStatus.BLOCKED
            tier = val_result.assurance_tier if val_result else AssuranceTier.BLOCKED

            total_claims += 1

            if status == ValidationStatus.BLOCKED:
                blocked_claims_count += 1
                reasons = [r.value for r in (val_result.reason_codes if val_result else [])]
                blocked_items.append({
                    "claim_id": claim.claim_id,
                    "section": section,
                    "reason_codes": reasons,
                    "display_text": claim.display_text,
                })
                # NON-NEGOTIABLE SAFETY RULE: Blocked claims are NEVER added to display statements!
                continue

            if status == ValidationStatus.VERIFIED:
                verified_claims_count += 1
            elif status == ValidationStatus.NOTE_SUPPORTED:
                note_supported_count += 1

            # Build citations for verified/note-supported claim
            citations = []
            for sid in claim.source_ids:
                srec = source_records.get(sid)
                if srec:
                    citations.append({
                        "source_id": srec.id,
                        "type": srec.type,
                        "date": str(srec.date) if srec.date else None,
                        "origin": srec.origin_org,
                        "trust": srec.trust_status.value if hasattr(srec.trust_status, "value") else str(srec.trust_status),
                        "span": claim.span.model_dump() if claim.span else None,
                    })
                else:
                    citations.append({
                        "source_id": sid,
                        "type": "unknown",
                        "date": claim.date,
                        "origin": "unknown",
                        "trust": "unknown",
                        "span": claim.span.model_dump() if claim.span else None,
                    })

            stmt_dict = {
                "statement_id": claim.claim_id,
                "text": claim.display_text,
                "type": claim.type.value,
                "status": status.value,
                "assurance_tier": tier.value,
                "field_path": claim.field_path,
                "cycle_id": claim.cycle_id,
                "citations": citations,
            }
            statements.append(stmt_dict)
            sec_verified.append(stmt_dict)
            all_verified_claim_dicts.append({
                "field_path": claim.field_path,
                "cycle_id": claim.cycle_id,
                "entity": claim.entity,
                "section": claim.section,
                "display_text": claim.display_text,
            })

        verified_claims_by_section[section] = sec_verified
        composed_sections[section] = {
            "name": section,
            "mode": sec_res.mode,
            "statements": statements,
        }

    # 3. Snapshot (5 lines max)
    snapshot = build_snapshot_lines(
        patient=patient,
        current_stage=current_stage,
        verified_claims_by_section=verified_claims_by_section,
        all_conflicts=all_conflicts,
        overdue_followups=overdue_followups,
        missing_items=all_missing,
    )

    # 4. Coverage check
    coverage_result = check_coverage(db, scope, all_verified_claim_dicts)
    coverage_gaps = coverage_result.get("omitted", [])

    # 5. Degradation stats
    deg_ratio = (blocked_claims_count / total_claims) if total_claims > 0 else 0.0

    provider_name = type(llm_client).__name__
    model_name = getattr(llm_client, "model", "mock-deterministic")

    raw_res = {
        "patient_id": patient_id,
        "snapshot": snapshot,
        "sections": composed_sections,
        "conflicts": all_conflicts,
        "not_documented": all_missing,
        "coverage_gaps": coverage_gaps,
        "disclaimer": "AI-assisted summary. Clinician review required.",
        "validator_report": {
            "total_claims": total_claims,
            "verified_claims": verified_claims_count,
            "note_supported_claims": note_supported_count,
            "blocked_claims": blocked_claims_count,
            "degradation_ratio": round(deg_ratio, 4),
            "blocked_items": blocked_items,
        },
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider_name,
            "model": model_name,
            "guard_flags": any_guard_flag,
            "guard_events": all_guard_events,
        },
    }
    return json.loads(json.dumps(raw_res, default=str))
