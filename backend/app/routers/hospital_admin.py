from typing import List, Optional
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.patient import Patient, DoctorPatient
from app.models.provenance import PatientHospitalAccess
from app.models.enums import UserRole, HospitalAccessStatus
from app.core.scope import require_roles
from app.core.audit import record_audit
from app.core.errors import AppException


router = APIRouter(prefix="/hospital-admin", tags=["hospital-admin"])


class DoctorAssignmentRequest(BaseModel):
    doctor_id: str
    patient_id: str


class DoctorAssignmentResponse(BaseModel):
    doctor_id: str
    doctor_username: str
    patient_id: str
    hospital_id: str
    status: str


class HospitalDoctorRead(BaseModel):
    id: str
    username: str
    role: str
    hospital_id: str


@router.post(
    "/doctor-assignments",
    response_model=DoctorAssignmentResponse,
    summary="Assign a doctor to a patient within the hospital's authorized scope",
)
async def assign_doctor_to_patient(
    req: DoctorAssignmentRequest,
    current_user: User = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Hospital Admin assigns a facility physician to a patient chart.
    Validates that:
    1. Patient exists (404).
    2. Hospital has an active patient_hospital_access grant for the patient (403).
    3. Doctor exists and is employed by the admin's hospital (403).
    """
    user_hospital_id = current_user.hospital_id or current_user.org_id

    # 1. Patient check
    patient = db.get(Patient, req.patient_id)
    if not patient:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Patient '{req.patient_id}' not found")

    # 2. Hospital access check
    pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == req.patient_id,
            PatientHospitalAccess.hospital_id == user_hospital_id,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if not pha and current_user.role != UserRole.ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hospital_id}' does not have active access to patient '{req.patient_id}'",
        )

    # 3. Doctor check
    doctor = db.get(User, req.doctor_id)
    if not doctor or doctor.role != UserRole.DOCTOR:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Physician user '{req.doctor_id}' not found",
        )

    doc_hosp = doctor.hospital_id or doctor.org_id
    if doc_hosp != user_hospital_id and current_user.role != UserRole.ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Physician '{doctor.username}' belongs to hospital '{doc_hosp}', not '{user_hospital_id}'",
        )

    # 4. Check / insert DoctorPatient assignment
    existing = db.scalar(
        select(DoctorPatient).where(
            DoctorPatient.doctor_id == doctor.id,
            DoctorPatient.patient_id == patient.id,
        )
    )
    if not existing:
        assignment = DoctorPatient(doctor_id=doctor.id, patient_id=patient.id)
        db.add(assignment)
        db.commit()

    record_audit(
        db,
        user_id=current_user.id,
        action="doctor_assigned",
        patient_id=patient.id,
        hospital_id=user_hospital_id,
        details={"doctor_id": doctor.id, "doctor_username": doctor.username},
    )

    return DoctorAssignmentResponse(
        doctor_id=doctor.id,
        doctor_username=doctor.username,
        patient_id=patient.id,
        hospital_id=user_hospital_id,
        status="assigned",
    )


@router.delete(
    "/doctor-assignments",
    response_model=DoctorAssignmentResponse,
    summary="Remove doctor assignment from a patient chart",
)
async def unassign_doctor_from_patient(
    doctor_id: str = Query(..., description="Doctor user ID"),
    patient_id: str = Query(..., description="Patient ID"),
    current_user: User = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Hospital Admin removes a physician assignment from a patient."""
    user_hospital_id = current_user.hospital_id or current_user.org_id
    doctor = db.get(User, doctor_id)
    if not doctor:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Doctor '{doctor_id}' not found")

    doc_hosp = doctor.hospital_id or doctor.org_id
    if doc_hosp != user_hospital_id and current_user.role != UserRole.ADMIN:
        raise AppException(status_code=403, code="FORBIDDEN", message="Doctor belongs to a different facility")

    db.execute(
        delete(DoctorPatient).where(
            DoctorPatient.doctor_id == doctor_id,
            DoctorPatient.patient_id == patient_id,
        )
    )
    db.commit()

    record_audit(
        db,
        user_id=current_user.id,
        action="doctor_unassigned",
        patient_id=patient_id,
        hospital_id=user_hospital_id,
        details={"doctor_id": doctor.id},
    )

    return DoctorAssignmentResponse(
        doctor_id=doctor.id,
        doctor_username=doctor.username,
        patient_id=patient_id,
        hospital_id=user_hospital_id,
        status="unassigned",
    )


@router.get(
    "/doctors",
    response_model=List[HospitalDoctorRead],
    summary="List doctors employed at this hospital",
)
async def list_hospital_doctors(
    current_user: User = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Returns all physicians in the current hospital admin's hospital."""
    user_hospital_id = current_user.hospital_id or current_user.org_id
    doctors = db.scalars(
        select(User).where(
            User.role == UserRole.DOCTOR,
            (User.hospital_id == user_hospital_id) | (User.org_id == user_hospital_id),
        )
    ).all()
    return [
        HospitalDoctorRead(
            id=d.id,
            username=d.username,
            role=d.role.value,
            hospital_id=d.hospital_id or d.org_id,
        )
        for d in doctors
    ]


@router.get(
    "/patient-assignments/{patient_id}",
    response_model=List[HospitalDoctorRead],
    summary="List doctors assigned to a patient from this hospital",
)
async def list_patient_doctor_assignments(
    patient_id: str = Path(...),
    current_user: User = Depends(require_roles(UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Returns all physicians from the admin's hospital assigned to this patient."""
    user_hospital_id = current_user.hospital_id or current_user.org_id
    assignments = db.scalars(
        select(User)
        .join(DoctorPatient, DoctorPatient.doctor_id == User.id)
        .where(
            DoctorPatient.patient_id == patient_id,
            (User.hospital_id == user_hospital_id) | (User.org_id == user_hospital_id),
        )
    ).all()
    return [
        HospitalDoctorRead(
            id=d.id,
            username=d.username,
            role=d.role.value,
            hospital_id=d.hospital_id or d.org_id,
        )
        for d in assignments
    ]
