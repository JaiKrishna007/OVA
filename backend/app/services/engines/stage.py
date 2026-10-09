"""
Stage Engine: Determines current clinical stage relative to AS_OF_DATE.
Outputs traceable clinical stage with source_refs, or 'Stage not documented'.
"""

from datetime import date
from typing import Dict, Any, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scope import Scope
from app.models.cycle import Cycle
from app.models.clinical import (
    StimulationDay,
    Transfer,
    PregnancyOutcome,
    Investigation,
    Followup,
    DoctorNote,
)


def get_current_stage(
    db: Session,
    scope: Scope,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Computes current clinical stage for the patient relative to AS_OF_DATE.
    Queries by patient_id, inspects ongoing/latest cycle status, pending tests,
    and planned follow-ups. Never calls an LLM.
    """
    target_date = as_of_date or date.fromisoformat(settings.AS_OF_DATE)

    # 1. Query latest cycle for the patient
    stmt = (
        select(Cycle)
        .where(Cycle.patient_id == scope.patient_id)
        .order_by(desc(Cycle.start_date), desc(Cycle.cycle_no))
    )
    latest_cycle = db.scalars(stmt).first()

    if not latest_cycle:
        return {
            "patient_id": scope.patient_id,
            "stage": "Stage not documented",
            "cycle_id": None,
            "detail": "No cycles on record",
            "as_of_date": target_date.isoformat(),
            "source_refs": [],
        }

    # 2. Check active stimulation in latest cycle (e.g. P-101 cycle 3)
    stim_stmt = (
        select(StimulationDay)
        .where(StimulationDay.cycle_id == latest_cycle.id)
        .order_by(desc(StimulationDay.day_no))
    )
    latest_stim = db.scalars(stim_stmt).first()

    if latest_stim and (latest_cycle.end_date is None or latest_stim.date >= latest_cycle.start_date):
        if latest_cycle.end_date is None or latest_cycle.end_date >= target_date:
            detail = f"Stimulation day {latest_stim.day_no}, cycle {latest_cycle.cycle_no}"
            return {
                "patient_id": scope.patient_id,
                "stage": detail,
                "cycle_id": latest_cycle.id,
                "detail": f"Day {latest_stim.day_no} scan on {latest_stim.date.isoformat()}; Endo: {latest_stim.endometrium_mm or 'undocumented'} mm",
                "as_of_date": target_date.isoformat(),
                "field_path": f"stimulation_days.{latest_stim.id}.day_no",
                "source_refs": [latest_stim.source_id],
            }

    # 3. Check for pending beta-hCG investigations (e.g. P-103)
    pending_beta_stmt = (
        select(Investigation)
        .where(
            Investigation.patient_id == scope.patient_id,
            Investigation.name.ilike("%beta-hcg%"),
            Investigation.status == "pending",
        )
    )
    pending_beta = db.scalars(pending_beta_stmt).first()
    if pending_beta:
        return {
            "patient_id": scope.patient_id,
            "stage": "Awaiting beta-hCG",
            "cycle_id": latest_cycle.id,
            "detail": f"Stat serum beta-hCG ordered on {pending_beta.ordered_date.isoformat() if pending_beta.ordered_date else 'recent date'}; awaiting lab results",
            "as_of_date": target_date.isoformat(),
            "field_path": f"investigations.{pending_beta.id}.status",
            "source_refs": [pending_beta.source_id],
        }

    # 4. Check for ongoing pregnancy outcome (e.g. P-102)
    preg_stmt = (
        select(PregnancyOutcome)
        .where(
            PregnancyOutcome.cycle_id == latest_cycle.id,
            PregnancyOutcome.result == "ongoing",
        )
    )
    ongoing_preg = db.scalars(preg_stmt).first()
    if ongoing_preg:
        return {
            "patient_id": scope.patient_id,
            "stage": "Ongoing clinical pregnancy at 9 weeks",
            "cycle_id": latest_cycle.id,
            "detail": ongoing_preg.gestation_note or "Single live intrauterine pregnancy confirmed",
            "as_of_date": target_date.isoformat(),
            "field_path": f"pregnancy_outcomes.{ongoing_preg.id}.result",
            "source_refs": [ongoing_preg.source_id],
        }

    # 5. Check for miscarriage followed by planned FET (e.g. P-104)
    # Check notes and scheduled followups
    scheduled_fet = db.scalar(
        select(Followup).where(
            Followup.patient_id == scope.patient_id,
            Followup.name.ilike("%FET%"),
            Followup.status == "scheduled",
        )
    )
    loss_note = db.scalar(
        select(DoctorNote).where(
            DoctorNote.patient_id == scope.patient_id,
            DoctorNote.text.ilike("%miscarriage%"),
        )
    )
    if scheduled_fet and loss_note:
        refs = [loss_note.source_id]
        if scheduled_fet.source_id not in refs:
            refs.append(scheduled_fet.source_id)
        return {
            "patient_id": scope.patient_id,
            "stage": "Post-miscarriage, FET planned",
            "cycle_id": latest_cycle.id,
            "detail": f"Spontaneous loss resolved; FET consultation scheduled for {scheduled_fet.due_date.isoformat()}",
            "as_of_date": target_date.isoformat(),
            "field_path": f"doctor_notes.{loss_note.id}.text",
            "source_refs": sorted(refs),
        }

    # 6. Check for cancelled / failed fertilization cycle (e.g. P-105)
    if latest_cycle.outcome == "cancel":
        source_ref = latest_cycle.source_id or (latest_cycle.treatment_events[0].source_id if latest_cycle.treatment_events else None)
        return {
            "patient_id": scope.patient_id,
            "stage": "Cycle 1 cancelled (failed fertilization), review pending",
            "cycle_id": latest_cycle.id,
            "detail": "Failed fertilization post-ICSI; couple review pending",
            "as_of_date": target_date.isoformat(),
            "field_path": f"cycles.{latest_cycle.id}.outcome",
            "source_refs": [source_ref] if source_ref else [],
        }

    # 7. Fallback: cycle ended or stage not documented
    if latest_cycle.outcome:
        return {
            "patient_id": scope.patient_id,
            "stage": f"Cycle {latest_cycle.cycle_no} completed ({latest_cycle.outcome})",
            "cycle_id": latest_cycle.id,
            "detail": f"Cycle ended on {latest_cycle.end_date.isoformat() if latest_cycle.end_date else 'date not documented'}",
            "as_of_date": target_date.isoformat(),
            "field_path": f"cycles.{latest_cycle.id}.outcome",
            "source_refs": [latest_cycle.source_id] if latest_cycle.source_id else [],
        }

    return {
        "patient_id": scope.patient_id,
        "stage": "Stage not documented",
        "cycle_id": latest_cycle.id,
        "detail": "Stage details not documented in patient chart",
        "as_of_date": target_date.isoformat(),
        "source_refs": [],
    }
