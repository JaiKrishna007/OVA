"""Audit log query endpoints — append-only read access only."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc, and_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.patient import Patient
from app.models.audit_log import AuditLog
from app.models.enums import UserRole
from app.schemas.audit_log import AuditLogRead
from app.core.scope import require_roles, get_current_user
from app.services.audit_service import AuditService, AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogRead])
async def get_audit_logs(
    # Pagination
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return (1–500)"),
    # Filters
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    user_id: Optional[str] = Query(None, description="Filter by acting user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event_type constant (e.g. PATIENT_VIEWED)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (success, failure, blocked, denied)"),
    date_from: Optional[str] = Query(None, description="ISO date lower bound (inclusive), e.g. 2025-01-01"),
    date_to: Optional[str] = Query(None, description="ISO date upper bound (inclusive), e.g. 2025-12-31"),
    # Auth
    admin_user: User = Depends(require_roles(
        UserRole.ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.OVA_ADMIN
    )),
    db: Session = Depends(get_db),
):
    """
    Retrieve audit logs with fine-grained filters.

    - **OVA_ADMIN**: sees all rows across all hospitals (platform view).
    - **HOSPITAL_ADMIN / ADMIN**: sees only rows where `org_id` matches their
      own hospital — cross-tenant isolation enforced server-side.
    - Supports filtering by patient, acting user, event type, outcome, and
      date range so that security teams can investigate specific incidents.
    """
    # ----- Build base WHERE clause (tenant-scoped) -----
    conditions = []

    if admin_user.role == UserRole.OVA_ADMIN:
        pass  # no org filter — full platform view
    else:
        user_hosp = admin_user.hospital_id or admin_user.org_id
        conditions.append(AuditLog.org_id == user_hosp)

    # ----- Optional filters -----
    if patient_id:
        # Extra cross-tenant patient guard for HOSPITAL_ADMIN
        if admin_user.role != UserRole.OVA_ADMIN:
            patient = db.get(Patient, patient_id)
            user_hosp = admin_user.hospital_id or admin_user.org_id
            if patient and patient.org_id != user_hosp:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: patient belongs to another organization",
                )
        conditions.append(AuditLog.patient_id == patient_id)

    if user_id:
        conditions.append(AuditLog.user_id == user_id)

    if event_type:
        conditions.append(AuditLog.event_type == event_type.upper())

    if outcome:
        conditions.append(AuditLog.outcome == outcome.lower())

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=422, detail="date_from must be ISO format (YYYY-MM-DD)")
        conditions.append(AuditLog.at >= dt_from)

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            # Treat as end-of-day by adding 23:59:59
            if "T" not in date_to:
                from datetime import timedelta
                dt_to = dt_to + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=422, detail="date_to must be ISO format (YYYY-MM-DD)")
        conditions.append(AuditLog.at < dt_to)

    # ----- Execute -----
    stmt = select(AuditLog)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(desc(AuditLog.at)).limit(limit)

    logs = db.scalars(stmt).all()
    return [AuditLogRead.model_validate(log) for log in logs]


@router.get("/patient/{patient_id}", response_model=List[AuditLogRead])
async def get_patient_activity(
    patient_id: str,
    limit: int = Query(100, ge=1, le=500),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    current_user: User = Depends(require_roles(
        UserRole.DOCTOR,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.OVA_ADMIN,
    )),
    db: Session = Depends(get_db),
):
    """
    Per-patient Activity feed for doctors.
    Returns all audit events touching this patient, newest first.
    Hospital scoping: DOCTOR/HOSPITAL_ADMIN see only events from their hospital.
    OVA_ADMIN sees all events across hospitals.
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found")

    conditions = [AuditLog.patient_id == patient_id]

    if current_user.role not in (UserRole.OVA_ADMIN, UserRole.ADMIN):
        user_hosp = current_user.hospital_id or current_user.org_id
        conditions.append(AuditLog.hospital_id == user_hosp)

    if event_type:
        conditions.append(AuditLog.event_type == event_type.upper())

    stmt = (
        select(AuditLog)
        .where(and_(*conditions))
        .order_by(desc(AuditLog.at))
        .limit(limit)
    )
    logs = db.scalars(stmt).all()
    return [AuditLogRead.model_validate(log) for log in logs]
