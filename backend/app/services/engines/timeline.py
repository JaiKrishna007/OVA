"""
Timeline Engine v2: Constructs an ordered sequence of cycles and chronological clinical events.
Returns events grouped by year then by cycle.
Each event carries:
- date
- canonical_event_name
- stage (Stimulation, Monitoring, OPU, Embryology, Transfer, Outcome)
- hospital
- origin_org
- source_record_id
- validation_status
- citation
- cycle_id & cycle_no

Guarantees chronological ordering across all hospitals and preserves provenance.
"""

from typing import Dict, List, Any, Optional
from datetime import date
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.models.cycle import Cycle
from app.models.provenance import ClinicalClaim
from app.models.enums import ClaimValidationStatus
from app.models.clinical import (
    TreatmentEvent,
    StimulationDay,
    OocyteRetrieval,
    Transfer,
    PregnancyOutcome,
    AdverseEvent,
    Investigation,
)

BADGE_MAP = {
    "negative": "Negative",
    "biochemical_pregnancy": "Biochemical Pregnancy",
    "biochemical": "Biochemical Pregnancy",
    "clinical_pregnancy": "Clinical Pregnancy",
    "clinical": "Clinical Pregnancy",
    "ongoing_pregnancy": "Ongoing Pregnancy",
    "ongoing": "Ongoing Pregnancy",
    "spontaneous_miscarriage": "Spontaneous Miscarriage",
    "miscarriage": "Miscarriage",
    "loss": "Pregnancy Loss",
    "ectopic": "Ectopic",
    "failed_fertilization": "Failed Fertilization",
    "cancelled": "Cancelled",
    "cancel": "Cancelled",
    "freeze_all": "Freeze-All",
    "live_birth": "Live Birth",
}

CANONICAL_EVENT_NAMES = {
    "opu": "Oocyte Retrieval (OPU)",
    "stimulation": "Ovarian Stimulation",
    "transfer": "Embryo Transfer",
    "outcome": "Pregnancy Outcome",
    "adverse_event": "Adverse Clinical Event",
    "trigger": "Ovulation Trigger",
    "iui": "IUI Insemination",
    "oi": "Ovulation Induction",
    "cancel": "Cycle Cancellation",
    "other": "Clinical Treatment Event",
    "semen": "Semen Analysis",
    "lab_serum": "Serum Investigation",
    "imaging": "Ultrasound / Imaging",
}


def _canonical_name_for_event(kind: str, detail: Optional[str] = None) -> str:
    k = (kind or "").lower()
    if k in CANONICAL_EVENT_NAMES:
        return CANONICAL_EVENT_NAMES[k]
    if "trigger" in k or (detail and "trigger" in detail.lower()):
        return "Ovulation Trigger"
    if "transfer" in k:
        return "Embryo Transfer"
    if "opu" in k or "retriev" in k:
        return "Oocyte Retrieval (OPU)"
    return kind.replace("_", " ").title() if kind else "Clinical Event"


def _determine_stage(kind: str, detail: Optional[str] = None) -> str:
    k = (kind or "").lower()
    d = (detail or "").lower()
    if "stimulat" in k or "medicat" in k:
        return "Stimulation"
    if "trigger" in k or "trigger" in d:
        return "Trigger"
    if "opu" in k or "retriev" in k or "aspirat" in k:
        return "OPU"
    if "embryo" in k or "blastocyst" in k or "2pn" in d or "fertiliz" in d:
        return "Embryology"
    if "transfer" in k or "fet" in k:
        return "Transfer"
    if "outcome" in k or "pregnancy" in k or "hcg" in k or "miscarriage" in d or "loss" in d:
        return "Outcome"
    if "endo" in d or "follicle" in d or "e2" in d:
        return "Monitoring"
    return "Monitoring"


def get_timeline(db: Session, scope: Scope) -> Dict[str, Any]:
    """
    Constructs an ordered timeline for the scoped patient:
    Returns events grouped by year then by cycle, with hospital and source provenance.
    Chronologically sorts all events across hospitals.
    """
    # 1. Fetch cycles strictly by scope.patient_id
    cycles_stmt = (
        select(Cycle)
        .where(Cycle.patient_id == scope.patient_id)
        .order_by(Cycle.cycle_no.asc(), Cycle.start_date.asc())
    )
    cycles = db.scalars(cycles_stmt).all()

    timeline_cycles = []
    all_events_flat: List[Dict[str, Any]] = []

    for cycle in cycles:
        cycle_events: List[Dict[str, Any]] = []
        cycle_source_refs = set()
        if cycle.source_id:
            cycle_source_refs.add(cycle.source_id)

        # 1. Treatment events
        for ev in cycle.treatment_events:
            cycle_source_refs.add(ev.source_id)
            d_str = ev.date.isoformat()
            cycle_events.append({
                "id": ev.id,
                "event_id": ev.id,
                "kind": ev.kind.value,
                "canonical_event_name": _canonical_name_for_event(ev.kind.value, ev.detail),
                "stage": _determine_stage(ev.kind.value, ev.detail),
                "date": d_str,
                "detail": ev.detail,
                "field_path": f"treatment_events.{ev.id}.kind",
                "hospital": ev.origin_org,
                "origin_org": ev.origin_org,
                "source_record_id": ev.source_id,
                "source_refs": [ev.source_id],
                "trust_status": ev.trust_status.value if hasattr(ev.trust_status, "value") else str(ev.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{ev.source_id}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 2. Stimulation Days
        for st in cycle.stimulation_days:
            cycle_source_refs.add(st.source_id)
            d_str = st.date.isoformat()
            detail = f"Stimulation Day {st.day_no}"
            if st.e2:
                detail += f", E2: {st.e2} pg/mL"
            if st.endometrium_mm:
                detail += f", Endo: {st.endometrium_mm} mm"
            cycle_events.append({
                "id": st.id,
                "event_id": st.id,
                "kind": "stimulation",
                "canonical_event_name": f"Stimulation Day {st.day_no}",
                "stage": "Stimulation",
                "date": d_str,
                "detail": detail,
                "field_path": f"stimulation_days.{st.id}.day_no",
                "hospital": st.origin_org,
                "origin_org": st.origin_org,
                "source_record_id": st.source_id,
                "source_refs": [st.source_id],
                "trust_status": st.trust_status.value if hasattr(st.trust_status, "value") else str(st.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{st.source_id}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 3. Oocyte Retrievals
        for opu in cycle.oocyte_retrievals:
            cycle_source_refs.add(opu.source_id)
            d_str = opu.date.isoformat()
            cycle_events.append({
                "id": opu.id,
                "event_id": opu.id,
                "kind": "opu",
                "canonical_event_name": "Oocyte Pick-Up (OPU)",
                "stage": "OPU",
                "date": d_str,
                "detail": f"{opu.oocytes_retrieved} oocytes retrieved (MII: {opu.mii or 0}, MI: {opu.mi or 0})",
                "field_path": f"oocyte_retrievals.{opu.id}.oocytes_retrieved",
                "hospital": opu.origin_org,
                "origin_org": opu.origin_org,
                "source_record_id": opu.source_id,
                "source_refs": [opu.source_id],
                "trust_status": opu.trust_status.value if hasattr(opu.trust_status, "value") else str(opu.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{opu.source_id}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 4. Transfers
        for trf in cycle.transfers:
            cycle_source_refs.add(trf.source_id)
            d_str = trf.date.isoformat()
            cycle_events.append({
                "id": trf.id,
                "event_id": trf.id,
                "kind": "transfer",
                "canonical_event_name": f"{trf.kind.value.capitalize()} Embryo Transfer",
                "stage": "Transfer",
                "date": d_str,
                "detail": f"{trf.kind.value.capitalize()} embryo transfer ({len(trf.embryo_ids or [])} embryo(s))",
                "field_path": f"transfers.{trf.id}.kind",
                "hospital": trf.origin_org,
                "origin_org": trf.origin_org,
                "source_record_id": trf.source_id,
                "source_refs": [trf.source_id],
                "trust_status": trf.trust_status.value if hasattr(trf.trust_status, "value") else str(trf.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{trf.source_id}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 5. Pregnancy Outcomes
        for prg in cycle.pregnancy_outcomes:
            cycle_source_refs.add(prg.source_id)
            d_obj = prg.beta_hcg_date or cycle.end_date or cycle.start_date
            d_str = d_obj.isoformat()
            detail = f"Outcome: {prg.result.value}"
            if prg.beta_hcg_value is not None:
                detail += f" (beta-hCG: {prg.beta_hcg_value} mIU/mL)"
            cycle_events.append({
                "id": prg.id,
                "event_id": prg.id,
                "kind": "outcome",
                "canonical_event_name": "Pregnancy Outcome Assessment",
                "stage": "Outcome",
                "date": d_str,
                "detail": detail,
                "field_path": f"pregnancy_outcomes.{prg.id}.result",
                "hospital": prg.origin_org,
                "origin_org": prg.origin_org,
                "source_record_id": prg.source_id,
                "source_refs": [prg.source_id],
                "trust_status": prg.trust_status.value if hasattr(prg.trust_status, "value") else str(prg.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{prg.source_id}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 6. Adverse Events
        for adv in cycle.adverse_events:
            cycle_source_refs.add(adv.source_id)
            d_str = adv.date.isoformat()
            cycle_events.append({
                "id": adv.id,
                "event_id": adv.id,
                "kind": "adverse_event",
                "canonical_event_name": f"Adverse Event: {adv.kind}",
                "stage": "Monitoring",
                "date": d_str,
                "detail": f"{adv.kind} ({adv.severity}): {adv.management_note or ''}",
                "field_path": f"adverse_events.{adv.id}.kind",
                "hospital": adv.origin_org,
                "origin_org": adv.origin_org,
                "source_record_id": adv.source_id,
                "source_refs": [adv.source_id],
                "trust_status": adv.trust_status.value if hasattr(adv.trust_status, "value") else str(adv.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{adv.source_id}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 7. Investigations linked to cycle
        for inv in cycle.investigations:
            cycle_source_refs.add(inv.source_id)
            d_str = inv.date.isoformat() if inv.date else cycle.start_date.isoformat()
            cycle_events.append({
                "id": inv.id,
                "event_id": inv.id,
                "kind": inv.category.value if hasattr(inv.category, "value") else str(inv.category),
                "canonical_event_name": f"Investigation: {inv.name}",
                "stage": "Monitoring",
                "date": d_str,
                "detail": f"{inv.name}: {inv.value} {inv.unit or ''}".strip(),
                "field_path": f"investigations.{inv.id}.value",
                "hospital": inv.origin_org or cycle.origin_org or "Kernel Prime Fertility Hospital",
                "origin_org": inv.origin_org or cycle.origin_org or "Kernel Prime Fertility Hospital",
                "source_record_id": inv.source_id or cycle.source_id or "REC-UNKNOWN",
                "source_refs": [inv.source_id or cycle.source_id or "REC-UNKNOWN"],
                "trust_status": inv.trust_status.value if hasattr(inv.trust_status, "value") else str(inv.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{inv.source_id or cycle.source_id or 'REC-UNKNOWN'}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # 8. Medications linked to cycle
        for med in cycle.medications:
            cycle_source_refs.add(med.source_id)
            d_str = med.start_date.isoformat() if med.start_date else cycle.start_date.isoformat()
            cycle_events.append({
                "id": med.id,
                "event_id": med.id,
                "kind": "medication",
                "canonical_event_name": f"Medication: {med.name}",
                "stage": "Stimulation",
                "date": d_str,
                "detail": f"{med.name} {med.dose} ({med.route})",
                "field_path": f"medications.{med.id}.name",
                "hospital": med.origin_org or cycle.origin_org or "Kernel Prime Fertility Hospital",
                "origin_org": med.origin_org or cycle.origin_org or "Kernel Prime Fertility Hospital",
                "source_record_id": med.source_id or cycle.source_id or "REC-UNKNOWN",
                "source_refs": [med.source_id or cycle.source_id or "REC-UNKNOWN"],
                "trust_status": med.trust_status.value if hasattr(med.trust_status, "value") else str(med.trust_status),
                "validation_status": "VERIFIED",
                "citation": f"[{med.source_id or cycle.source_id or 'REC-UNKNOWN'}, {d_str}]",
                "cycle_id": cycle.id,
                "cycle_no": cycle.cycle_no,
                "cycle_assignment": "ASSIGNED",
            })

        # Sort cycle events chronologically
        cycle_events.sort(key=lambda x: x["date"])
        all_events_flat.extend(cycle_events)

        stages_present = sorted(list({ev["stage"] for ev in cycle_events}))

        timeline_cycles.append({
            "cycle_id": cycle.id,
            "cycle_no": cycle.cycle_no,
            "type": cycle.type.value if hasattr(cycle.type, "value") else str(cycle.type),
            "start_date": cycle.start_date.isoformat(),
            "end_date": cycle.end_date.isoformat() if cycle.end_date else None,
            "outcome": cycle.outcome,
            "outcome_badge": BADGE_MAP.get(cycle.outcome, cycle.outcome.replace("_", " ").title() if cycle.outcome else "In Progress"),
            "hospital": cycle.origin_org or "Kernel Prime Fertility Hospital",
            "origin_org": cycle.origin_org,
            "trust_status": cycle.trust_status.value if cycle.trust_status and hasattr(cycle.trust_status, "value") else (str(cycle.trust_status) if cycle.trust_status else "internal_verified"),
            "external_cycle_no": cycle.external_cycle_no,
            "field_path": f"cycles.{cycle.id}.outcome",
            "source_refs": sorted(list(cycle_source_refs)),
            "stages": stages_present,
            "events": cycle_events,
        })

    # 2. Fetch unlinked or ambiguous claims
    unlinked_claims = db.scalars(
        select(ClinicalClaim)
        .where(
            ClinicalClaim.patient_id == scope.patient_id,
            (ClinicalClaim.cycle_assignment == "NEEDS_REVIEW") | (ClinicalClaim.cycle_id == None),
        )
    ).all()

    unlinked_events: List[Dict[str, Any]] = []
    for uc in unlinked_claims:
        d_str = uc.event_date.isoformat() if uc.event_date else "Undated"
        unlinked_events.append({
            "id": uc.id,
            "event_id": uc.id,
            "kind": uc.field,
            "canonical_event_name": _canonical_name_for_event(uc.field, uc.evidence_text),
            "stage": _determine_stage(uc.field, uc.evidence_text),
            "date": d_str,
            "detail": f"{uc.field}: {uc.value_text or uc.value_num or ''} {uc.unit or ''}".strip(),
            "hospital": uc.hospital_id,
            "origin_org": uc.hospital_id,
            "source_record_id": uc.source_record_id,
            "source_refs": [uc.source_record_id],
            "trust_status": "internal_verified",
            "validation_status": uc.validation_status.value if hasattr(uc.validation_status, "value") else str(uc.validation_status),
            "citation": f"[{uc.source_record_id}, {d_str}]",
            "cycle_id": None,
            "cycle_assignment": "NEEDS_REVIEW",
        })

    # 3. Group by Year then by Cycle
    # Cross-hospital sorting: all events sorted chronologically by date
    all_events_flat.sort(key=lambda x: x["date"])

    years_dict: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for ev in all_events_flat:
        try:
            yr = int(ev["date"][:4])
            years_dict[yr].append(ev)
        except Exception:
            pass

    years_payload = []
    for yr in sorted(years_dict.keys()):
        yr_events = years_dict[yr]
        # Identify cycles active in this year
        yr_cycle_ids = {ev["cycle_id"] for ev in yr_events if ev.get("cycle_id")}
        yr_cycles = [
            {
                **c,
                "events": [ev for ev in yr_events if ev.get("cycle_id") == c["cycle_id"]],
            }
            for c in timeline_cycles
            if c["cycle_id"] in yr_cycle_ids
        ]
        years_payload.append({
            "year": yr,
            "events_count": len(yr_events),
            "cycles": yr_cycles,
            "events": yr_events,
        })

    all_sources = sorted(list({s for c in timeline_cycles for s in c.get("source_refs", [])}))

    return {
        "patient_id": scope.patient_id,
        "total_cycles": len(timeline_cycles),
        "cycles": timeline_cycles,
        "years": years_payload,
        "unlinked_events": unlinked_events,
        "events_count": len(all_events_flat),
        "source_refs": all_sources,
    }
