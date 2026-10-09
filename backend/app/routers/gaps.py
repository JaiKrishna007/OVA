from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.enums import UserRole, GapStatus, HospitalAccessLevel, HospitalAccessStatus
from app.models.provenance import DocumentationGap, PatientHospitalAccess
from app.models.user import User
from app.models.patient import Patient, DoctorPatient
from app.schemas.provenance import DocumentationGapRead, GapAcknowledgeRequest
from app.core.scope import require_roles
from app.core.audit import record_audit
from app.services.audit_service import AuditService, AuditEvent
from app.core.errors import AppException
from app.services.engines.gaps import recompute_and_persist_gaps

router = APIRouter(tags=["gaps"])


def _verify_patient_access(db: Session, user: User, patient_id: str, require_write: bool = False) -> None:
    """Verifies user RBAC and hospital access for patient gaps."""
    if user.role == UserRole.OVA_ADMIN:
        raise AppException(status_code=403, code="FORBIDDEN", message="OVA administrators cannot access clinical documentation gaps.")

    if user.role == UserRole.PATIENT:
        raise AppException(status_code=403, code="FORBIDDEN", message="Clinical documentation gaps are restricted from patient view.")

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
        raise AppException(status_code=403, code="FORBIDDEN", message="Hospital has READ_ONLY access; gaps cannot be acknowledged.")


@router.get(
    "/patients/{patient_id}/gaps",
    response_model=List[DocumentationGapRead],
    summary="Get patient clinical documentation gaps",
    description="Retrieve all persistent documentation gaps for a patient, running the protocol gap engine.",
)
async def get_patient_gaps(
    patient_id: str = Path(..., description="Patient ID (e.g. P-103)"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    _verify_patient_access(db, current_user, patient_id)

    # Recompute to ensure fresh, idempotent state
    recomputed = recompute_and_persist_gaps(db, patient_id)
    db.commit()

    AuditService.log_from_user(
        db, current_user, AuditEvent.GAP_DETECTED,
        patient_id=patient_id,
        details={"gaps_count": len(recomputed)},
    )

    return recomputed


@router.post(
    "/gaps/{gap_id}/acknowledge",
    response_model=DocumentationGapRead,
    summary="Clinician acknowledges a documentation gap",
    description="Records doctor acknowledgment and explanatory note for a missing protocol record.",
)
@router.post(
    "/gaps/{gap_id}/ack",
    response_model=DocumentationGapRead,
    summary="Clinician acknowledges a documentation gap (alias)",
    include_in_schema=False,
)
async def acknowledge_gap(
    gap_id: str = Path(..., description="Gap ID (e.g. GAP-001)"),
    request: GapAcknowledgeRequest = GapAcknowledgeRequest(),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    gap = db.get(DocumentationGap, gap_id)
    if not gap:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Documentation gap '{gap_id}' not found.")

    _verify_patient_access(db, current_user, gap.patient_id, require_write=True)

    gap.status = GapStatus.ACKNOWLEDGED
    gap.acknowledged_by = current_user.id
    gap.acknowledged_at = datetime.now(timezone.utc)
    if request.note:
        gap.note = request.note

    AuditService.log_from_user(
        db, current_user, AuditEvent.CONFLICT_ACKNOWLEDGED,
        patient_id=gap.patient_id,
        details={
            "gap_id": gap.id,
            "rule_id": gap.rule_id,
            "note": request.note,
        },
    )

    db.commit()
    db.refresh(gap)

    return gap
