from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.enums import UserRole, ConflictStatus, HospitalAccessLevel, HospitalAccessStatus
from app.models.user import User
from app.models.patient import Patient, DoctorPatient
from app.models.provenance import ConflictRecord, PatientHospitalAccess
from app.schemas.provenance import ConflictRead, ConflictAcknowledgeRequest
from app.core.scope import require_roles
from app.core.audit import record_audit
from app.services.audit_service import AuditService, AuditEvent
from app.core.errors import AppException
from app.services.engines.conflicts import recompute_and_persist_conflicts

router = APIRouter(tags=["conflicts"])


def _verify_patient_access(db: Session, user: User, patient_id: str, require_write: bool = False) -> None:
    """Verifies user RBAC and hospital access for patient conflicts."""
    if user.role == UserRole.OVA_ADMIN:
        raise AppException(status_code=403, code="FORBIDDEN", message="OVA administrators cannot access clinical conflict records.")

    if user.role == UserRole.PATIENT:
        raise AppException(status_code=403, code="FORBIDDEN", message="Clinical conflict records are restricted from patient view.")

    patient = db.get(Patient, patient_id)
    if not patient:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Patient '{patient_id}' not found.")

    if user.role == UserRole.DOCTOR:
        assignment = db.scalars(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == user.id,
                DoctorPatient.patient_id == patient_id,
            )
        ).first()
        if not assignment:
            raise AppException(status_code=403, code="FORBIDDEN", message=f"Doctor is not assigned to patient '{patient_id}'.")

    user_hosp = user.hospital_id or user.org_id
    pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == patient_id,
            PatientHospitalAccess.hospital_id == user_hosp,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if not pha and user.role != UserRole.ADMIN:
        raise AppException(status_code=403, code="FORBIDDEN", message=f"Hospital '{user_hosp}' does not have active access to patient '{patient_id}'.")

    if require_write and pha and pha.access_level == HospitalAccessLevel.READ_ONLY:
        raise AppException(status_code=403, code="FORBIDDEN", message="Hospital has READ_ONLY access; conflicts cannot be acknowledged.")


@router.get(
    "/patients/{patient_id}/conflicts",
    response_model=List[ConflictRead],
    summary="Get patient clinical conflicts",
    description="Retrieve all persistent clinical conflicts for a patient, running the engine to detect contradictions across records.",
)
async def get_patient_conflicts(
    patient_id: str = Path(..., description="Patient ID (e.g. P-102)"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    _verify_patient_access(db, current_user, patient_id)

    # Recompute to ensure fresh, idempotent state
    recomputed = recompute_and_persist_conflicts(db, patient_id)
    db.commit()

    AuditService.log_from_user(
        db, current_user, AuditEvent.CONFLICT_DETECTED,
        patient_id=patient_id,
        details={"conflicts_count": len(recomputed)},
    )

    return recomputed


@router.post(
    "/conflicts/{conflict_id}/acknowledge",
    response_model=ConflictRead,
    summary="Clinician acknowledges a conflict",
    description="Records doctor acknowledgment and explanatory note. NEVER modifies any claim value or selects a winner.",
)
@router.post(
    "/conflicts/{conflict_id}/ack",
    response_model=ConflictRead,
    summary="Clinician acknowledges a conflict (alias)",
    include_in_schema=False,
)
async def acknowledge_conflict(
    conflict_id: str = Path(..., description="Conflict ID (e.g. CONF-001)"),
    request: ConflictAcknowledgeRequest = ConflictAcknowledgeRequest(),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    conflict = db.get(ConflictRecord, conflict_id)
    if not conflict:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Conflict '{conflict_id}' not found.")

    _verify_patient_access(db, current_user, conflict.patient_id, require_write=True)

    # Record acknowledgment without altering any clinical data
    conflict.status = ConflictStatus.ACKNOWLEDGED
    conflict.acknowledged_by = current_user.id
    conflict.acknowledged_at = datetime.now(timezone.utc)
    if request.note:
        conflict.note = request.note

    AuditService.log_from_user(
        db, current_user, AuditEvent.CONFLICT_ACKNOWLEDGED,
        patient_id=conflict.patient_id,
        details={
            "conflict_id": conflict.id,
            "field": conflict.field,
            "note": request.note,
        },
    )

    db.commit()
    db.refresh(conflict)

    return conflict
