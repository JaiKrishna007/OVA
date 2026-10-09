from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.patient import Patient, DoctorPatient
from app.models.clinical import Followup
from app.models.enums import UserRole
from app.models.user import User

from app.core.scope import require_roles
from app.core.audit import record_audit
from app.core.errors import AppException
from app.schemas.responses import FollowupUpdateRequest, FollowupItemResponse

router = APIRouter(prefix="/followups", tags=["followups"])


@router.patch(
    "/{followup_id}",
    response_model=FollowupItemResponse,
    summary="Update follow-up item",
    description="Update status or due date of a pending or overdue follow-up item. Audit logged and restricted to authorized doctor or staff.",
)
async def update_followup(
    followup_id: str,
    update_data: FollowupUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update a followup item's status, due date, or name.
    Verifies that the target patient belongs to the user's organization,
    and if doctor, that the doctor is assigned to the patient.
    """
    followup = db.get(Followup, followup_id)
    if not followup:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Followup with id '{followup_id}' was not found",
        )

    patient = db.get(Patient, followup.patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{followup.patient_id}' not found",
        )

    user_hosp = current_user.hospital_id or current_user.org_id
    from app.models.provenance import PatientHospitalAccess
    from app.models.enums import HospitalAccessLevel, HospitalAccessStatus
    from sqlalchemy import select

    pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == patient.id,
            PatientHospitalAccess.hospital_id == user_hosp,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if not pha and current_user.role != UserRole.ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hosp}' does not have active access to patient '{patient.id}'",
        )

    if pha and pha.access_level == HospitalAccessLevel.READ_ONLY:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hosp}' has READ_ONLY access; followups cannot be updated",
        )

    if current_user.role == UserRole.DOCTOR:
        assignment = (
            db.query(DoctorPatient)
            .filter(
                DoctorPatient.doctor_id == current_user.id,
                DoctorPatient.patient_id == followup.patient_id,
            )
            .first()
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message="Doctor is not assigned to this patient",
            )

    # Apply updates
    if update_data.status is not None:
        followup.status = update_data.status
    if update_data.due_date is not None:
        followup.due_date = update_data.due_date
    if update_data.name is not None:
        followup.name = update_data.name

    db.commit()
    db.refresh(followup)

    record_audit(
        db,
        user_id=current_user.id,
        action="followup_update",
        patient_id=followup.patient_id,
    )

    return FollowupItemResponse(
        id=followup.id,
        patient_id=followup.patient_id,
        cycle_id=followup.cycle_id,
        kind=followup.kind,
        name=followup.name,
        status=followup.status.value if hasattr(followup.status, "value") else str(followup.status),
        due_date=followup.due_date,
        source_id=followup.source_id,
        source_refs=[followup.source_id] if followup.source_id else [],
    )
