"""
Cycle Grouping Service: Assigns clinical claims and events to treatment cycles (OI, IUI, IVF/ICSI, FET).
Enforces:
1. Event type sequential progression: stimulation -> trigger -> OPU -> embryology -> transfer -> beta-hCG/outcome.
2. Cycle closure: starting a new cycle when a new stimulation appears after a closed outcome.
3. Date proximity & hospital origin checks.
4. Ambiguous events are explicitly marked cycle_assignment="NEEDS_REVIEW" (never silently guessed).
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.cycle import Cycle
from app.models.enums import CycleType, TrustStatus, ClaimValidationStatus
from app.models.provenance import ClinicalClaim
from app.models.clinical import (
    TreatmentEvent,
    StimulationDay,
    OocyteRetrieval,
    Transfer,
    PregnancyOutcome,
)

logger = logging.getLogger(__name__)

# Canonical sequential stage progression ranks
STAGE_RANKS: Dict[str, int] = {
    "stimulation": 1,
    "monitoring": 1,
    "antral_follicle_count": 1,
    "endometrial_thickness": 1,
    "trigger": 2,
    "opu": 3,
    "oocytes_retrieved": 3,
    "mature_oocytes_mii": 3,
    "embryology": 4,
    "fertilized_2pn": 4,
    "blastocysts_count": 4,
    "embryos_frozen": 4,
    "embryos_created": 4,
    "transfer": 5,
    "embryo_transfer": 5,
    "fet": 5,
    "fresh_transfer": 5,
    "iui": 3,
    "oi": 2,
    "outcome": 6,
    "pregnancy_test": 6,
    "clinical_pregnancy": 6,
    "pregnancy_outcome": 6,
    "beta_hcg": 6,
}

# Closed outcome keywords
CLOSED_OUTCOMES = {
    "negative",
    "biochemical",
    "biochemical_pregnancy",
    "clinical",
    "clinical_pregnancy",
    "ongoing",
    "ongoing_pregnancy",
    "loss",
    "miscarriage",
    "spontaneous_miscarriage",
    "ectopic",
    "failed_fertilization",
    "cancelled",
    "cancel",
    "freeze_all",
    "live_birth",
}


def get_field_stage(field: str) -> str:
    """Maps a clinical field or event kind to its cycle stage name."""
    f = field.lower().strip()
    if f in ("stimulation", "stimulation_day", "medication", "antral_follicle_count"):
        return "stimulation"
    if f in ("trigger", "ovitrelle", "hcg_trigger"):
        return "trigger"
    if f in ("opu", "oocytes_retrieved", "mature_oocytes_mii", "oocyte_retrieval"):
        return "opu"
    if f in ("embryology", "fertilized_2pn", "blastocysts_count", "embryos_frozen", "embryos_created", "embryo"):
        return "embryology"
    if f in ("transfer", "embryo_transfer", "fet", "fresh_transfer", "transfer_kind"):
        return "transfer"
    if f in ("outcome", "pregnancy_test", "clinical_pregnancy", "pregnancy_outcome", "beta_hcg"):
        return "outcome"
    if f in ("endometrial_thickness", "estradiol", "progesterone", "lh", "fsh"):
        return "monitoring"
    if f in ("iui",):
        return "iui"
    if f in ("oi",):
        return "oi"
    return "general"


def infer_cycle_type_from_fields(fields: List[str]) -> CycleType:
    """Infers CycleType from a list of clinical fields present in the cycle."""
    field_set = {f.lower() for f in fields}
    if any("opu" in f or "oocyte" in f for f in field_set):
        if any("icsi" in f for f in field_set):
            return CycleType.ICSI
        return CycleType.IVF
    if any("fet" in f or "frozen" in f for f in field_set):
        return CycleType.FET
    if any("transfer" in f for f in field_set):
        return CycleType.FET
    if any("iui" in f for f in field_set):
        return CycleType.IUI
    if any("oi" in f for f in field_set):
        return CycleType.OI
    return CycleType.IVF


def group_claims_into_cycles(
    db: Session,
    patient_id: str,
    hospital_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Groups verified clinical claims and clinical events for a patient into chronological cycles.
    - Preserves existing cycles if aligned.
    - Spawns new cycles when stimulation begins after a closed outcome or large gap.
    - Marks ambiguous assignments with cycle_assignment="NEEDS_REVIEW".
    """
    # 1. Fetch all existing cycles for this patient ordered by start date
    existing_cycles = db.scalars(
        select(Cycle)
        .where(Cycle.patient_id == patient_id)
        .order_by(Cycle.cycle_no.asc(), Cycle.start_date.asc())
    ).all()

    # 2. Fetch all verified claims for this patient ordered by event date
    claims = db.scalars(
        select(ClinicalClaim)
        .where(
            ClinicalClaim.patient_id == patient_id,
            ClinicalClaim.validation_status == ClaimValidationStatus.VERIFIED,
        )
        .order_by(ClinicalClaim.event_date.asc().nulls_last(), ClinicalClaim.created_at.asc())
    ).all()

    assigned_count = 0
    needs_review_count = 0
    new_cycles_created = 0

    # Track active cycle list (including newly created ones)
    cycles_list = list(existing_cycles)

    for claim in claims:
        if not claim.event_date:
            # Undated claims cannot be reliably grouped into time-delimited cycles
            claim.cycle_assignment = "NEEDS_REVIEW"
            needs_review_count += 1
            continue

        stage = get_field_stage(claim.field)
        stage_rank = STAGE_RANKS.get(stage, 0)
        c_date = claim.event_date

        # Check if already assigned to a cycle that exists
        if claim.cycle_id:
            matching_cycle = next((c for c in cycles_list if c.id == claim.cycle_id), None)
            if matching_cycle:
                claim.cycle_assignment = "ASSIGNED"
                assigned_count += 1
                continue

        # Find best matching cycle among existing cycles
        best_cycle: Optional[Cycle] = None
        is_ambiguous = False

        for c in cycles_list:
            c_start = c.start_date
            c_end = c.end_date or (c_start + timedelta(days=90))

            # Proximity window: [-5 days before start, end + 14 days]
            win_start = c_start - timedelta(days=5)
            win_end = c_end + timedelta(days=14)

            if win_start <= c_date <= win_end:
                # If cycle has a closed outcome, events occurring strictly AFTER the outcome cannot join it!
                if c.outcome and c.end_date and c_date > c.end_date:
                    if stage == "stimulation":
                        # Stimulation after closed outcome -> definitely belongs to next cycle!
                        continue
                    else:
                        is_ambiguous = True
                        break

                # Hospital check: if cycle origin differs from claim hospital
                if c.origin_org and claim.hospital_id and c.origin_org != claim.hospital_id:
                    # Flag as ambiguous unless cross-hospital link is confirmed
                    is_ambiguous = True
                    break

                best_cycle = c
                break

        # Sequence violation check: OPU (rank 3) cannot follow Transfer (rank 5) or Outcome (rank 6)
        if best_cycle and not is_ambiguous:
            # Check if cycle already reached later irreversible stages
            existing_trf = [ev for ev in best_cycle.transfers if ev.date <= c_date]
            existing_outcomes = [po for po in best_cycle.pregnancy_outcomes if (po.beta_hcg_date or best_cycle.end_date or best_cycle.start_date) <= c_date]
            if (existing_trf or existing_outcomes) and stage in ("opu", "trigger"):
                is_ambiguous = True
                best_cycle = None

        if is_ambiguous:
            claim.cycle_id = None
            claim.cycle_assignment = "NEEDS_REVIEW"
            needs_review_count += 1
            continue

        if best_cycle:
            claim.cycle_id = best_cycle.id
            claim.cycle_assignment = "ASSIGNED"
            assigned_count += 1
            if stage == "outcome" and not best_cycle.outcome:
                best_cycle.outcome = str(claim.value_text or "clinical").lower()
                best_cycle.end_date = c_date
            elif c_date and (not best_cycle.end_date or c_date > best_cycle.end_date):
                best_cycle.end_date = c_date
        else:
            # No existing cycle covers this date.
            # If this is a cycle initiator (stimulation, monitoring, or OPU): start a new cycle!
            if stage in ("stimulation", "opu", "transfer", "iui", "oi"):
                next_cycle_no = (max([c.cycle_no for c in cycles_list], default=0)) + 1
                new_cycle_id = f"CY-{patient_id}-{next_cycle_no}"
                new_cycle_type = infer_cycle_type_from_fields([claim.field])
                if stage == "transfer":
                    new_cycle_type = CycleType.FET

                new_cycle = Cycle(
                    id=new_cycle_id,
                    patient_id=patient_id,
                    cycle_no=next_cycle_no,
                    type=new_cycle_type,
                    start_date=c_date,
                    end_date=None,
                    outcome=None,
                    origin_org=claim.hospital_id or (cycles_list[0].origin_org if cycles_list else "ORG-Y"),
                    org_id=claim.hospital_id or (cycles_list[0].org_id if cycles_list else "ORG-Y"),
                    source_id=claim.source_record_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(new_cycle)
                cycles_list.append(new_cycle)
                new_cycles_created += 1

                claim.cycle_id = new_cycle.id
                claim.cycle_assignment = "ASSIGNED"
                assigned_count += 1
            else:
                # Standalone test/investigation with no surrounding cycle
                claim.cycle_id = None
                claim.cycle_assignment = "NEEDS_REVIEW"
                needs_review_count += 1

    db.flush()

    return {
        "patient_id": patient_id,
        "assigned_claims": assigned_count,
        "needs_review_claims": needs_review_count,
        "new_cycles_created": new_cycles_created,
        "total_cycles": len(cycles_list),
    }
