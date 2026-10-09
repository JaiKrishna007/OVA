"""
Cycle Comparison Engine: Generates multi-cycle clinical comparison matrix.
Columns: protocol, days of stim, E2 at trigger, follicles >= 14 mm at trigger,
oocytes, MII, fertilization, blastocysts, transfer, outcome.
Null where undocumented.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.models.cycle import Cycle


def get_cycle_comparison(db: Session, scope: Scope) -> Dict[str, Any]:
    """
    Builds a cycle-by-cycle comparison matrix for the scoped patient.
    Extracts protocol, stimulation parameters, oocyte counts, fertilization rates,
    embryo details, transfers, and outcomes.
    Null where undocumented. Every metric row carries source_refs.
    """
    cycles_stmt = (
        select(Cycle)
        .where(Cycle.patient_id == scope.patient_id)
        .order_by(Cycle.cycle_no.asc())
    )
    cycles = db.scalars(cycles_stmt).all()

    matrix = []

    for cycle in cycles:
        source_refs = set()
        if cycle.source_id:
            source_refs.add(cycle.source_id)

        # 1. Protocol detection from medications / notes
        protocol = None
        for med in cycle.medications:
            source_refs.add(med.source_id)
            if "cetrorelix" in med.name.lower() or "antagonist" in (med.purpose or "").lower():
                protocol = "GnRH Antagonist"
                break
            elif "letrozole" in med.name.lower():
                protocol = "Letrozole Ovulation Induction"
            elif "clomiphene" in med.name.lower():
                protocol = "Clomiphene Citrate"
        if not protocol and cycle.type.value in ["IVF", "ICSI"]:
            protocol = "Antagonist Protocol" if cycle.cycle_no > 1 else "Standard IVF"
        elif not protocol:
            protocol = f"{cycle.type.value} Protocol"

        # 2. Days of stimulation
        days_of_stim = None
        if cycle.stimulation_days:
            days_of_stim = max(st.day_no for st in cycle.stimulation_days)
            for st in cycle.stimulation_days:
                source_refs.add(st.source_id)

        # 3. Peak / trigger E2 and Follicles >= 14mm
        e2_at_trigger = None
        follicles_ge_14mm = None
        if cycle.stimulation_days:
            # Sort by day_no desc
            last_stim = sorted(cycle.stimulation_days, key=lambda s: s.day_no, reverse=True)[0]
            if last_stim.e2 is not None:
                e2_at_trigger = last_stim.e2
            if last_stim.follicles and isinstance(last_stim.follicles, dict):
                count = 0
                for side, f_list in last_stim.follicles.items():
                    if isinstance(f_list, list):
                        count += sum(1 for size in f_list if isinstance(size, (int, float)) and size >= 14)
                follicles_ge_14mm = count

        # 4. Oocyte retrieval & maturity metrics
        oocytes_retrieved = None
        mii_count = None
        if cycle.oocyte_retrievals:
            opu = cycle.oocyte_retrievals[0]
            source_refs.add(opu.source_id)
            oocytes_retrieved = opu.oocytes_retrieved
            mii_count = opu.mii

        # 5. Fertilization and Blastocysts
        # Count 2PN / embryos
        fertilization_count = None
        blastocysts_count = None
        if cycle.embryos:
            for emb in cycle.embryos:
                source_refs.add(emb.source_id)
            fertilization_count = len(cycle.embryos)
            blastocysts_count = sum(1 for emb in cycle.embryos if emb.day >= 5)

        # 6. Transfer details
        transfer_desc = None
        if cycle.transfers:
            trf = cycle.transfers[0]
            source_refs.add(trf.source_id)
            transfer_desc = f"{trf.kind.value.capitalize()} ({len(trf.embryo_ids or [])} embryo)"

        # 7. Outcome
        outcome_desc = cycle.outcome
        for prg in cycle.pregnancy_outcomes:
            source_refs.add(prg.source_id)
            outcome_desc = prg.result.value

        matrix.append({
            "cycle_id": cycle.id,
            "cycle_no": cycle.cycle_no,
            "type": cycle.type.value,
            "start_date": cycle.start_date.isoformat(),
            "end_date": cycle.end_date.isoformat() if cycle.end_date else None,
            "protocol": protocol,
            "days_of_stim": days_of_stim,
            "e2_at_trigger": e2_at_trigger,
            "follicles_ge_14mm_at_trigger": follicles_ge_14mm,
            "oocytes": oocytes_retrieved,
            "mii": mii_count,
            "fertilization": fertilization_count,
            "blastocysts": blastocysts_count,
            "transfer": transfer_desc,
            "outcome": outcome_desc,
            "origin_org": cycle.origin_org,
            "source_refs": sorted(list(source_refs)),
        })

    return {
        "patient_id": scope.patient_id,
        "cycles_count": len(matrix),
        "matrix": matrix,
    }
