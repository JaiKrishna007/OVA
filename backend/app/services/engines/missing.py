"""
Missing Data Detector Engine: Rule-based detector for expected clinical workup items.
Evaluates clinical profile, cycles, and diagnostics against protocol rules.
Outputs items as {item, reason, rule_id, patient_id}.
"""

from typing import Dict, List, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.models.patient import Patient, DoctorPatient
from app.models.cycle import Cycle
from app.models.source_record import SourceRecord
from app.models.clinical import Investigation
from app.models.enums import UserRole

# Configurable rule set for clinical expectations
EXPECTED_RULES = [
    {
        "rule_id": "RULE_EXPECT_MALE_FACTOR_WORKUP",
        "item": "Partner Semen Analysis",
        "description": "No partner semen analysis on file for infertility workup.",
    },
    {
        "rule_id": "RULE_EXPECT_TUBAL_PATENCY_WORKUP",
        "item": "Hysterosalpingography (HSG) Report",
        "description": "No HSG or tubal patency evaluation report on file.",
    },
]


def detect_missing_data(db: Session, scope: Scope) -> List[Dict[str, Any]]:
    """
    Evaluates expected clinical workup items and gaps for the scoped patient.
    Enforces doctor scope (unassigned doctors receive []).
    Delegates to v2 documentation gaps engine.
    """
    if scope.user and scope.user.role == UserRole.DOCTOR:
        user_id = scope.user.id
        from app.models.user import User
        db_user = db.scalars(select(User).where((User.id == user_id) | (User.username == scope.user.username))).first()
        actual_doctor_id = db_user.id if db_user else user_id
        assigned = db.scalars(
            select(DoctorPatient).where(
                (DoctorPatient.doctor_id == actual_doctor_id) | (DoctorPatient.doctor_id == user_id),
                DoctorPatient.patient_id == scope.patient_id,
            )
        ).first()
        if not assigned:
            return []

    from app.services.engines.gaps import recompute_and_persist_gaps
    gaps = recompute_and_persist_gaps(db, scope.patient_id)
    return [
        {
            "absence_id": g.id,
            "patient_id": g.patient_id,
            "item": g.expected_item,
            "rule_id": g.rule_id,
            "reason": g.note or f"Missing documentation for {g.expected_item}",
            "description": g.note or f"Missing documentation for {g.expected_item}",
        }
        for g in gaps
    ]
