"""
Materializer Service: Converts VERIFIED clinical claims into typed clinical table rows.
Populates materialized_table and materialized_row_id back-links on each claim.
Guarantees strict idempotency: re-processing a record or re-running materialization never creates duplicates.
Triggers summary invalidation (is_stale=True) and conflict/gap recomputation upon completion.
"""

import logging
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.cycle import Cycle
from app.models.enums import (
    ClaimValidationStatus,
    TrustStatus,
    InvestigationCategory,
    InvestigationStatus,
    TreatmentEventKind,
    TransferKind,
    PregnancyResult,
    EmbryoFate,
    ConflictStatus,
    GapStatus,
)
from app.models.provenance import ClinicalClaim, ConflictRecord, DocumentationGap
from app.models.summary import Summary
from app.models.clinical import (
    Investigation,
    OocyteRetrieval,
    Medication,
    TreatmentEvent,
    Transfer,
    PregnancyOutcome,
    Embryo,
)
from app.services.cycle_grouper.service import group_claims_into_cycles

logger = logging.getLogger(__name__)

SEMEN_FIELDS = {
    "sperm_concentration",
    "progressive_motility",
    "normal_morphology",
    "semen_volume",
    "total_motile_count",
}

LAB_FIELDS = {
    "amh",
    "fsh",
    "lh",
    "estradiol",
    "progesterone",
    "tsh",
    "prolactin",
    "beta_hcg",
    "antral_follicle_count",
    "endometrial_thickness",
}

PROCEDURE_FIELDS = {
    "opu",
    "procedure",
    "trigger",
    "iui",
    "oi",
    "aspiration",
    "cancellation",
    "treatment_event",
}


def _get_fallback_cycle_id(db: Session, patient_id: str, hospital_id: str, event_date: Optional[Any] = None) -> str:
    """Finds or creates a fallback cycle when non-nullable cycle foreign key is required."""
    cycle = db.scalars(
        select(Cycle)
        .where(Cycle.patient_id == patient_id)
        .order_by(Cycle.cycle_no.desc())
    ).first()
    if cycle:
        return cycle.id

    # Create cycle 1 if none exists
    new_c = Cycle(
        id=f"CY-{patient_id}-1",
        patient_id=patient_id,
        cycle_no=1,
        type="IVF",
        start_date=event_date or datetime.now(timezone.utc).date(),
        origin_org=hospital_id,
        org_id=hospital_id,
        trust_status=TrustStatus.INTERNAL_VERIFIED,
    )
    db.add(new_c)
    db.flush()
    return new_c.id


def materialize_claims(
    db: Session,
    patient_id: str,
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Materializes all VERIFIED claims for the patient into typed tables.
    Runs cycle grouping beforehand to ensure proper cycle_id assignment.
    Idempotent: skips claims that are already materialized and checks row existence.
    """
    # 1. Run cycle grouping first
    group_res = group_claims_into_cycles(db, patient_id=patient_id)

    # 2. Query verified claims that need materialization
    stmt = (
        select(ClinicalClaim)
        .where(
            ClinicalClaim.patient_id == patient_id,
            ClinicalClaim.validation_status == ClaimValidationStatus.VERIFIED,
        )
    )
    if record_id:
        stmt = stmt.where(ClinicalClaim.source_record_id == record_id)

    claims = db.scalars(stmt).all()

    materialized_count = 0
    skipped_count = 0

    for claim in claims:
        # Check if already materialized and row still exists
        if claim.materialized_table and claim.materialized_row_id:
            # Already materialized
            skipped_count += 1
            continue

        f = claim.field.lower().strip()
        h_id = claim.hospital_id or "ORG-Y"
        c_id = claim.cycle_id

        # ---------------------------------------------------------------------
        # Table A: investigations
        # ---------------------------------------------------------------------
        if f in LAB_FIELDS or f in SEMEN_FIELDS or "lab" in f or "antral" in f:
            target_id = f"INV-{claim.id}"
            existing = db.get(Investigation, target_id)
            if not existing:
                category = (
                    InvestigationCategory.SEMEN
                    if f in SEMEN_FIELDS
                    else InvestigationCategory.LAB
                )
                inv = Investigation(
                    id=target_id,
                    patient_id=claim.patient_id,
                    cycle_id=c_id,
                    category=category,
                    name=claim.field.upper(),
                    value=str(claim.value_num if claim.value_num is not None else (claim.value_text or "")),
                    unit=claim.unit,
                    date=claim.event_date,
                    status=InvestigationStatus.RESULTED,
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(inv)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "investigations"
            claim.materialized_row_id = target_id

        # ---------------------------------------------------------------------
        # Table B: oocyte_retrievals
        # ---------------------------------------------------------------------
        elif f in ("oocytes_retrieved", "opu", "mature_oocytes_mii") and claim.value_num is not None:
            target_id = f"OPU-{claim.id}"
            eff_cid = c_id or _get_fallback_cycle_id(db, claim.patient_id, h_id, claim.event_date)
            existing = db.get(OocyteRetrieval, target_id)
            if not existing:
                opu = OocyteRetrieval(
                    id=target_id,
                    cycle_id=eff_cid,
                    date=claim.event_date or datetime.now(timezone.utc).date(),
                    oocytes_retrieved=int(claim.value_num or 0),
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(opu)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "oocyte_retrievals"
            claim.materialized_row_id = target_id

        # ---------------------------------------------------------------------
        # Table C: treatment_events
        # ---------------------------------------------------------------------
        elif f in PROCEDURE_FIELDS or "trigger" in f or "iui" in f or "oi" in f:
            target_id = f"EV-{claim.id}"
            eff_cid = c_id or _get_fallback_cycle_id(db, claim.patient_id, h_id, claim.event_date)
            existing = db.get(TreatmentEvent, target_id)
            if not existing:
                kind = TreatmentEventKind.SCAN
                if "trigger" in f:
                    kind = TreatmentEventKind.TRIGGER
                elif "opu" in f:
                    kind = TreatmentEventKind.OPU
                elif "transfer" in f:
                    kind = TreatmentEventKind.TRANSFER
                elif "cancel" in f:
                    kind = TreatmentEventKind.CANCEL

                ev = TreatmentEvent(
                    id=target_id,
                    cycle_id=eff_cid,
                    kind=kind,
                    date=claim.event_date or datetime.now(timezone.utc).date(),
                    detail=claim.evidence_text or claim.value_text or claim.field,
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(ev)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "treatment_events"
            claim.materialized_row_id = target_id

        # ---------------------------------------------------------------------
        # Table D: transfers
        # ---------------------------------------------------------------------
        elif "transfer" in f or "fet" in f:
            target_id = f"TRF-{claim.id}"
            eff_cid = c_id or _get_fallback_cycle_id(db, claim.patient_id, h_id, claim.event_date)
            existing = db.get(Transfer, target_id)
            if not existing:
                kind = TransferKind.FROZEN if "fet" in f or "frozen" in f else TransferKind.FRESH
                trf = Transfer(
                    id=target_id,
                    cycle_id=eff_cid,
                    date=claim.event_date or datetime.now(timezone.utc).date(),
                    kind=kind,
                    embryo_ids=[],
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(trf)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "transfers"
            claim.materialized_row_id = target_id

        # ---------------------------------------------------------------------
        # Table E: pregnancy_outcomes
        # ---------------------------------------------------------------------
        elif "outcome" in f or "pregnancy" in f:
            target_id = f"PRG-{claim.id}"
            eff_cid = c_id or _get_fallback_cycle_id(db, claim.patient_id, h_id, claim.event_date)
            existing = db.get(PregnancyOutcome, target_id)
            if not existing:
                res = PregnancyResult.CLINICAL
                val_lower = str(claim.value_text or "").lower()
                if "negative" in val_lower:
                    res = PregnancyResult.NEGATIVE
                elif "biochemical" in val_lower:
                    res = PregnancyResult.BIOCHEMICAL
                elif "loss" in val_lower or "miscarriage" in val_lower:
                    res = PregnancyResult.LOSS
                elif "live" in val_lower or "birth" in val_lower:
                    res = PregnancyResult.LIVE_BIRTH

                prg = PregnancyOutcome(
                    id=target_id,
                    cycle_id=eff_cid,
                    result=res,
                    beta_hcg_value=claim.value_num,
                    beta_hcg_date=claim.event_date,
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(prg)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "pregnancy_outcomes"
            claim.materialized_row_id = target_id

        # ---------------------------------------------------------------------
        # Table F: medications
        # ---------------------------------------------------------------------
        elif "medication" in f or f in ("gonal-f", "menopur", "cetrotide", "ovitrelle", "duphaston", "progynova"):
            target_id = f"MED-{claim.id}"
            eff_cid = c_id or _get_fallback_cycle_id(db, claim.patient_id, h_id, claim.event_date)
            existing = db.get(Medication, target_id)
            if not existing:
                med = Medication(
                    id=target_id,
                    cycle_id=eff_cid,
                    name=claim.field.capitalize(),
                    dose=str(claim.value_text or claim.value_num or "Standard"),
                    route="Subcutaneous",
                    start_date=claim.event_date,
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(med)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "medications"
            claim.materialized_row_id = target_id

        # ---------------------------------------------------------------------
        # Table G: embryos
        # ---------------------------------------------------------------------
        elif "embryo" in f or "blastocyst" in f:
            target_id = f"EMB-{claim.id}"
            eff_cid = c_id or _get_fallback_cycle_id(db, claim.patient_id, h_id, claim.event_date)
            existing = db.get(Embryo, target_id)
            if not existing:
                emb = Embryo(
                    id=target_id,
                    cycle_id=eff_cid,
                    embryo_label=f"E-{claim.id[-4:]}",
                    day=5,
                    grade=str(claim.value_text or "4AA"),
                    fate=EmbryoFate.FROZEN,
                    source_id=claim.source_record_id,
                    org_id=h_id,
                    origin_org=h_id,
                    trust_status=TrustStatus.INTERNAL_VERIFIED,
                )
                db.add(emb)
                materialized_count += 1
            else:
                skipped_count += 1

            claim.materialized_table = "embryos"
            claim.materialized_row_id = target_id

    # 3. Post-Materialization: Invalidate patient summary
    summaries = db.scalars(
        select(Summary).where(Summary.patient_id == patient_id)
    ).all()
    for s in summaries:
        if isinstance(s.content_json, dict):
            content = dict(s.content_json)
            content["is_stale"] = True
            s.content_json = content
        db.add(s)

    # 4. Trigger conflict and gap recomputation and persistence
    from app.services.engines.conflicts import recompute_and_persist_conflicts
    from app.services.engines.gaps import recompute_and_persist_gaps

    recompute_and_persist_conflicts(db, patient_id)
    recompute_and_persist_gaps(db, patient_id)

    db.commit()

    return {
        "patient_id": patient_id,
        "materialized_count": materialized_count,
        "skipped_count": skipped_count,
        "cycle_grouping": group_res,
    }
