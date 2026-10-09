"""
Follow-ups Engine: Analyzes scheduled appointments, repeats, and pending investigations.
Detects overdue items relative to AS_OF_DATE.
"""

from datetime import date
from typing import Dict, List, Any, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scope import Scope
from app.models.clinical import Followup, Investigation
from app.models.enums import FollowupStatus, InvestigationStatus


def get_followups(
    db: Session,
    scope: Scope,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Retrieves all follow-up actions and pending investigations for the scoped patient.
    Flags items with due_date < AS_OF_DATE as overdue.
    Every output item includes source_refs and field_path.
    """
    target_date = as_of_date or date.fromisoformat(settings.AS_OF_DATE)

    # 1. Query followups table strictly by scope.patient_id
    stmt = (
        select(Followup)
        .where(Followup.patient_id == scope.patient_id)
        .order_by(Followup.due_date.asc())
    )
    db_followups = db.scalars(stmt).all()

    all_items = []
    overdue_items = []
    pending_items = []
    scheduled_items = []
    done_items = []

    for fol in db_followups:
        # Compute effective status based on AS_OF_DATE
        eff_status = fol.status.value
        if fol.status != FollowupStatus.DONE and fol.due_date < target_date:
            eff_status = "overdue"

        item = {
            "id": fol.id,
            "category": "followup",
            "kind": fol.kind,
            "name": fol.name,
            "status": eff_status,
            "original_status": fol.status.value,
            "due_date": fol.due_date.isoformat(),
            "cycle_id": fol.cycle_id,
            "field_path": f"followups.{fol.id}.status",
            "source_refs": [fol.source_id],
            "origin_org": fol.origin_org,
            "trust_status": fol.trust_status.value,
        }

        all_items.append(item)
        if eff_status == "overdue":
            overdue_items.append(item)
        elif eff_status == "scheduled":
            scheduled_items.append(item)
        elif eff_status == "pending":
            pending_items.append(item)
        elif eff_status == "done":
            done_items.append(item)

    # 2. Query pending investigations as pending follow-up items
    inv_stmt = (
        select(Investigation)
        .where(
            Investigation.patient_id == scope.patient_id,
            Investigation.status == InvestigationStatus.PENDING,
        )
        .order_by(desc(Investigation.ordered_date))
    )
    pending_invs = db.scalars(inv_stmt).all()

    for inv in pending_invs:
        item = {
            "id": inv.id,
            "category": "pending_investigation",
            "kind": inv.category.value,
            "name": inv.name,
            "status": "pending",
            "original_status": inv.status.value,
            "due_date": inv.ordered_date.isoformat() if inv.ordered_date else None,
            "cycle_id": inv.cycle_id,
            "field_path": f"investigations.{inv.id}.status",
            "source_refs": [inv.source_id],
            "origin_org": inv.origin_org,
            "trust_status": inv.trust_status.value,
        }
        all_items.append(item)
        pending_items.append(item)

    return {
        "patient_id": scope.patient_id,
        "as_of_date": target_date.isoformat(),
        "total_count": len(all_items),
        "overdue_count": len(overdue_items),
        "pending_count": len(pending_items),
        "scheduled_count": len(scheduled_items),
        "done_count": len(done_items),
        "items": all_items,
        "overdue": overdue_items,
        "pending": pending_items,
        "scheduled": scheduled_items,
        "done": done_items,
    }
