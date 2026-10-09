"""
Coverage Checker Engine: Assesses whether all critical 'must-mention' facts
(cycle outcomes, adverse events, active conflicts, and frozen embryos)
are addressed by a generated summary or list of claims.
"""

from typing import Dict, List, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.models.cycle import Cycle
from app.models.clinical import AdverseEvent, Embryo
from app.services.engines.conflicts import detect_conflicts


def check_coverage(
    db: Session,
    scope: Scope,
    claims: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates a list of claims against patient must-mention items.
    Must-mention items:
    1. Each cycle's outcome
    2. Each adverse event
    3. Every active conflict detected on the patient
    4. Every frozen embryo count / batch
    Returns covered and omitted items and a calculated coverage percentage.
    """
    must_mention: List[Dict[str, Any]] = []

    # 1. Each cycle outcome
    cycles = db.scalars(select(Cycle).where(Cycle.patient_id == scope.patient_id)).all()
    for cycle in cycles:
        if cycle.outcome:
            must_mention.append({
                "item_id": f"MUST-OUTCOME-{cycle.id}",
                "entity": "cycle_outcome",
                "cycle_id": cycle.id,
                "field_path": f"cycles.{cycle.id}.outcome",
                "label": f"Cycle {cycle.cycle_no} outcome ({cycle.outcome})",
                "source_id": cycle.source_id,
            })

    # 2. Each adverse event
    for cycle in cycles:
        for adv in cycle.adverse_events:
            must_mention.append({
                "item_id": f"MUST-ADV-{adv.id}",
                "entity": "adverse_event",
                "cycle_id": cycle.id,
                "field_path": f"adverse_events.{adv.id}.kind",
                "label": f"Adverse event: {adv.kind} ({adv.severity})",
                "source_id": adv.source_id,
            })

    # 3. Active conflicts
    conflicts = detect_conflicts(db, scope)
    for conf in conflicts:
        must_mention.append({
            "item_id": f"MUST-CONF-{conf['conflict_id']}",
            "entity": "conflict",
            "cycle_id": conf.get("cycle_id"),
            "field_path": conf.get("field_path"),
            "label": f"Conflict on {conf.get('field')}: {conf.get('description')}",
            "source_id": conf.get("source_id_a"),
        })

    # 4. Frozen embryos
    frozen_embryos = []
    for cycle in cycles:
        cycle_frozen = [e for e in cycle.embryos if e.fate.value == "frozen"]
        if cycle_frozen:
            frozen_embryos.extend(cycle_frozen)
            must_mention.append({
                "item_id": f"MUST-FROZEN-{cycle.id}",
                "entity": "frozen_embryos",
                "cycle_id": cycle.id,
                "field_path": f"embryos.{cycle_frozen[0].id}.fate",
                "label": f"Cycle {cycle.cycle_no} has {len(cycle_frozen)} frozen embryo(s)",
                "source_id": cycle_frozen[0].source_id,
            })

    # Match against claims
    covered = []
    omitted = []

    for item in must_mention:
        is_covered = False
        target_path = item.get("field_path")
        target_cycle = item.get("cycle_id")
        target_entity = item.get("entity")

        for claim in claims:
            # Check direct field_path match
            if target_path and claim.get("field_path") == target_path:
                is_covered = True
                break
            # Check entity and cycle match
            if target_cycle and claim.get("cycle_id") == target_cycle:
                if claim.get("entity") == target_entity or claim.get("section") in [target_entity, "outcomes_pregnancy", "adverse_events"]:
                    is_covered = True
                    break

        if is_covered:
            covered.append(item)
        else:
            omitted.append(item)

    total = len(must_mention)
    coverage_score = (len(covered) / total) if total > 0 else 1.0

    return {
        "patient_id": scope.patient_id,
        "total_must_mention": total,
        "covered_count": len(covered),
        "omitted_count": len(omitted),
        "coverage_score": round(coverage_score, 4),
        "covered": covered,
        "omitted": omitted,
        "must_mention_items": must_mention,
    }
