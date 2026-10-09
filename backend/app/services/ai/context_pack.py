from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.scope import Scope
from app.models import (
    Patient,
    Cycle,
    Investigation,
    Medication,
    StimulationDay,
    OocyteRetrieval,
    Embryo,
    Transfer,
    PregnancyOutcome,
    AdverseEvent,
    DoctorNote,
    SourceRecord,
)
from app.services.engines.conflicts import detect_conflicts
from app.services.engines.missing import detect_missing_data
from app.services.engines.stage import get_current_stage


SECTIONS = [
    "profile_diagnosis",
    "prior_cycles",
    "protocols_medications",
    "follicular_development",
    "oocyte_retrieval",
    "embryo_details",
    "outcomes_pregnancy",
    "adverse_events",
    "current_stage",
]


def build_section_context_pack(
    db: Session,
    scope: Scope,
    section: str,
    all_conflicts: Optional[List[Dict[str, Any]]] = None,
    all_missing: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Builds a focused, scoped context pack for a single clinical summary section.
    Includes only relevant structured rows, note texts with spans, and filtered detector items.
    """
    patient_id = scope.patient_id
    if not patient_id:
        raise ValueError("Scope must include patient_id")

    if all_conflicts is None:
        all_conflicts = detect_conflicts(db, scope)

    if all_missing is None:
        all_missing = detect_missing_data(db, scope)

    structured_rows: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []
    spans: List[Dict[str, Any]] = []
    section_conflicts: List[Dict[str, Any]] = []
    section_missing: List[Dict[str, Any]] = []

    # 1. Section: profile_diagnosis
    if section == "profile_diagnosis":
        patient = db.get(Patient, patient_id)
        first_rec = db.scalars(
            select(SourceRecord)
            .where(SourceRecord.patient_id == patient_id)
            .order_by(SourceRecord.date.asc())
        ).first()
        p_source_id = first_rec.id if first_rec else None

        if patient:
            # Baseline fields
            structured_rows.append({
                "table": "patients",
                "row_id": patient.id,
                "column": "blood_group",
                "field_path": f"patients.{patient.id}.blood_group",
                "cycle_id": None,
                "value": patient.blood_group,
                "unit": None,
                "date": None,
                "source_id": p_source_id,
            })
            if patient.bmi is not None:
                structured_rows.append({
                    "table": "patients",
                    "row_id": patient.id,
                    "column": "bmi",
                    "field_path": f"patients.{patient.id}.bmi",
                    "cycle_id": None,
                    "value": patient.bmi,
                    "unit": "kg/m2",
                    "date": None,
                    "source_id": p_source_id,
                })
        # Baseline investigations (cycle_id is None or category in lab, semen, genetic)
        invs = db.scalars(
            select(Investigation)
            .where(Investigation.patient_id == patient_id)
            .order_by(Investigation.date.asc())
        ).all()
        for inv in invs:
            if inv.cycle_id is None or inv.category in ("lab", "semen", "genetic"):
                structured_rows.append({
                    "table": "investigations",
                    "row_id": inv.id,
                    "column": "value",
                    "field_path": f"investigations.{inv.id}.value",
                    "cycle_id": inv.cycle_id,
                    "value": inv.value,
                    "unit": inv.unit,
                    "date": str(inv.date) if inv.date else None,
                    "source_id": inv.source_id,
                })
        # Filter detector items
        section_conflicts = [c for c in all_conflicts if "investigations" in (c.get("field_path") or "")]
        section_missing = [m for m in all_missing if any(k in m.get("rule_id", "") for k in ("AMH", "SEMEN", "TSH", "CARRIER", "HSG", "PELVIC"))]

    # 2. Section: prior_cycles
    elif section == "prior_cycles":
        cycles = db.scalars(
            select(Cycle)
            .where(Cycle.patient_id == patient_id)
            .order_by(Cycle.cycle_no.asc())
        ).all()
        for cy in cycles:
            cy_type_val = cy.type.value if hasattr(cy.type, "value") else str(cy.type)
            structured_rows.append({
                "table": "cycles",
                "row_id": cy.id,
                "column": "type",
                "field_path": f"cycles.{cy.id}.type",
                "cycle_id": cy.id,
                "value": cy_type_val,
                "unit": None,
                "date": str(cy.start_date) if cy.start_date else None,
                "source_id": cy.source_id,
            })
            structured_rows.append({
                "table": "cycles",
                "row_id": cy.id,
                "column": "outcome",
                "field_path": f"cycles.{cy.id}.outcome",
                "cycle_id": cy.id,
                "value": cy.outcome or "in_progress",
                "unit": None,
                "date": str(cy.start_date) if cy.start_date else None,
                "source_id": cy.source_id,
            })
        section_conflicts = [c for c in all_conflicts if "cycles" in (c.get("field_path") or "")]

    # 3. Section: protocols_medications
    elif section == "protocols_medications":
        meds = db.scalars(
            select(Medication)
            .join(Cycle, Medication.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(Medication.start_date.asc())
        ).all()
        for med in meds:
            structured_rows.append({
                "table": "medications",
                "row_id": med.id,
                "column": "dose",
                "field_path": f"medications.{med.id}.dose",
                "cycle_id": med.cycle_id,
                "value": med.dose,
                "unit": None,
                "date": str(med.start_date) if med.start_date else None,
                "source_id": med.source_id,
            })
            structured_rows.append({
                "table": "medications",
                "row_id": med.id,
                "column": "name",
                "field_path": f"medications.{med.id}.name",
                "cycle_id": med.cycle_id,
                "value": med.name,
                "unit": None,
                "date": str(med.start_date) if med.start_date else None,
                "source_id": med.source_id,
            })

    # 4. Section: follicular_development
    elif section == "follicular_development":
        stims = db.scalars(
            select(StimulationDay)
            .join(Cycle, StimulationDay.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(StimulationDay.date.asc())
        ).all()
        for st in stims:
            if st.endometrium_mm is not None:
                structured_rows.append({
                    "table": "stimulation_days",
                    "row_id": st.id,
                    "column": "endometrium_mm",
                    "field_path": f"stimulation_days.{st.id}.endometrium_mm",
                    "cycle_id": st.cycle_id,
                    "value": st.endometrium_mm,
                    "unit": "mm",
                    "date": str(st.date) if st.date else None,
                    "source_id": st.source_id,
                })
            if st.e2 is not None:
                structured_rows.append({
                    "table": "stimulation_days",
                    "row_id": st.id,
                    "column": "e2",
                    "field_path": f"stimulation_days.{st.id}.e2",
                    "cycle_id": st.cycle_id,
                    "value": st.e2,
                    "unit": "pg/mL",
                    "date": str(st.date) if st.date else None,
                    "source_id": st.source_id,
                })

    # 5. Section: oocyte_retrieval
    elif section == "oocyte_retrieval":
        opus = db.scalars(
            select(OocyteRetrieval)
            .join(Cycle, OocyteRetrieval.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(OocyteRetrieval.date.asc())
        ).all()
        for opu in opus:
            structured_rows.append({
                "table": "oocyte_retrievals",
                "row_id": opu.id,
                "column": "oocytes_retrieved",
                "field_path": f"oocyte_retrievals.{opu.id}.oocytes_retrieved",
                "cycle_id": opu.cycle_id,
                "value": opu.oocytes_retrieved,
                "unit": None,
                "date": str(opu.date) if opu.date else None,
                "source_id": opu.source_id,
            })
            if opu.mii is not None:
                structured_rows.append({
                    "table": "oocyte_retrievals",
                    "row_id": opu.id,
                    "column": "mii",
                    "field_path": f"oocyte_retrievals.{opu.id}.mii",
                    "cycle_id": opu.cycle_id,
                    "value": opu.mii,
                    "unit": None,
                    "date": str(opu.date) if opu.date else None,
                    "source_id": opu.source_id,
                })
        section_conflicts = [c for c in all_conflicts if "oocyte" in (c.get("field_path") or "").lower() or "OPU" in c.get("id", "")]

    # 6. Section: embryo_details
    elif section == "embryo_details":
        embryos = db.scalars(
            select(Embryo)
            .join(Cycle, Embryo.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(Embryo.id.asc())
        ).all()
        for emb in embryos:
            structured_rows.append({
                "table": "embryos",
                "row_id": emb.id,
                "column": "grade",
                "field_path": f"embryos.{emb.id}.grade",
                "cycle_id": emb.cycle_id,
                "value": emb.grade,
                "unit": None,
                "date": None,
                "source_id": emb.source_id,
            })
            structured_rows.append({
                "table": "embryos",
                "row_id": emb.id,
                "column": "fate",
                "field_path": f"embryos.{emb.id}.fate",
                "cycle_id": emb.cycle_id,
                "value": emb.fate,
                "unit": None,
                "date": None,
                "source_id": emb.source_id,
            })
            if emb.pgt_status:
                structured_rows.append({
                    "table": "embryos",
                    "row_id": emb.id,
                    "column": "pgt_status",
                    "field_path": f"embryos.{emb.id}.pgt_status",
                    "cycle_id": emb.cycle_id,
                    "value": emb.pgt_status,
                    "unit": None,
                    "date": None,
                    "source_id": emb.source_id,
                })

    # 7. Section: outcomes_pregnancy
    elif section == "outcomes_pregnancy":
        transfers = db.scalars(
            select(Transfer)
            .join(Cycle, Transfer.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(Transfer.date.asc())
        ).all()
        for tr in transfers:
            structured_rows.append({
                "table": "transfers",
                "row_id": tr.id,
                "column": "kind",
                "field_path": f"transfers.{tr.id}.kind",
                "cycle_id": tr.cycle_id,
                "value": tr.kind,
                "unit": None,
                "date": str(tr.date) if tr.date else None,
                "source_id": tr.source_id,
            })
        outcomes = db.scalars(
            select(PregnancyOutcome)
            .join(Cycle, PregnancyOutcome.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(PregnancyOutcome.id.asc())
        ).all()
        for out in outcomes:
            structured_rows.append({
                "table": "pregnancy_outcomes",
                "row_id": out.id,
                "column": "result",
                "field_path": f"pregnancy_outcomes.{out.id}.result",
                "cycle_id": out.cycle_id,
                "value": out.result,
                "unit": None,
                "date": str(out.beta_hcg_date) if out.beta_hcg_date else None,
                "source_id": out.source_id,
            })
            if out.beta_hcg_value is not None:
                structured_rows.append({
                    "table": "pregnancy_outcomes",
                    "row_id": out.id,
                    "column": "beta_hcg_value",
                    "field_path": f"pregnancy_outcomes.{out.id}.beta_hcg_value",
                    "cycle_id": out.cycle_id,
                    "value": out.beta_hcg_value,
                    "unit": "mIU/mL",
                    "date": str(out.beta_hcg_date) if out.beta_hcg_date else None,
                    "source_id": out.source_id,
                })
        section_conflicts = [c for c in all_conflicts if "outcome" in (c.get("field_path") or "").lower() or "pregnancy" in (c.get("field_path") or "").lower()]

    # 8. Section: adverse_events
    elif section == "adverse_events":
        advs = db.scalars(
            select(AdverseEvent)
            .join(Cycle, AdverseEvent.cycle_id == Cycle.id)
            .where(Cycle.patient_id == patient_id)
            .order_by(AdverseEvent.date.asc())
        ).all()
        for adv in advs:
            structured_rows.append({
                "table": "adverse_events",
                "row_id": adv.id,
                "column": "kind",
                "field_path": f"adverse_events.{adv.id}.kind",
                "cycle_id": adv.cycle_id,
                "value": adv.kind,
                "unit": None,
                "date": str(adv.date) if adv.date else None,
                "source_id": adv.source_id,
            })
            structured_rows.append({
                "table": "adverse_events",
                "row_id": adv.id,
                "column": "severity",
                "field_path": f"adverse_events.{adv.id}.severity",
                "cycle_id": adv.cycle_id,
                "value": adv.severity,
                "unit": None,
                "date": str(adv.date) if adv.date else None,
                "source_id": adv.source_id,
            })

    # 9. Section: current_stage
    elif section == "current_stage":
        stage_data = get_current_stage(db, scope)
        stage_text = stage_data.get("stage", "Stage not documented")
        structured_rows.append({
            "table": "stage",
            "row_id": "current",
            "column": "stage",
            "field_path": None,
            "cycle_id": None,
            "value": stage_text,
            "unit": None,
            "date": None,
            "source_id": None,
        })

    # Retrieve relevant source notes for this patient
    records = db.scalars(
        select(SourceRecord)
        .where(SourceRecord.patient_id == patient_id)
        .order_by(SourceRecord.date.asc())
    ).all()

    for rec in records:
        if rec.type in (
            "doctor_note",
            "doctor_notes",
            "progress_note",
            "clinical_note",
            "consultation_note",
            "procedure_note",
            "discharge_summary",
            "referral_letter",
            "lab_report",
            "opu_embryology_report",
            "opu_report",
            "stimulation_chart",
        ):
            # Check for known clinical spans (e.g., spontaneous miscarriage in P-104 REC-0404)
            if "spontaneous miscarriage" in rec.content_text and section == "outcomes_pregnancy":
                idx = rec.content_text.find("spontaneous miscarriage")
                spans.append({
                    "record_id": rec.id,
                    "cycle_id": rec.cycle_id,
                    "start": idx,
                    "end": idx + len("spontaneous miscarriage"),
                    "text": "spontaneous miscarriage",
                    "date": str(rec.date) if rec.date else None,
                })
            notes.append({
                "record_id": rec.id,
                "cycle_id": rec.cycle_id,
                "date": str(rec.date) if rec.date else None,
                "type": rec.type,
                "author": rec.author,
                "origin_org": rec.origin_org,
                "trust_status": rec.trust_status,
                "content_text": rec.content_text,
            })

    return {
        "section": section,
        "patient_id": patient_id,
        "structured_rows": structured_rows,
        "notes": notes,
        "spans": spans,
        "conflicts": section_conflicts,
        "missing_items": section_missing,
    }
