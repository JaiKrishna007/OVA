from dataclasses import dataclass
from typing import Optional, List, Callable
from fastapi import Depends, Header, Path, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
import jwt

from app.db.session import get_db
from app.models.user import User
from app.models.patient import Patient, DoctorPatient
from app.models.cycle import Cycle
from app.models.enums import UserRole, HospitalAccessLevel, HospitalAccessStatus
from app.models.provenance import PatientHospitalAccess
from app.core.security import decode_access_token
from app.core.errors import AppException


@dataclass
class Scope:
    """Access scope object restricting database queries to authorized org, hospital, patient, and cycle."""

    user: User
    patient_id: str
    cycle_id: Optional[str] = None
    org_id: str = ""
    hospital_id: str = ""
    access_level: HospitalAccessLevel = HospitalAccessLevel.READ_WRITE


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Extracts and validates JWT Bearer token, returning the authenticated User."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppException(
            status_code=401,
            code="UNAUTHORIZED",
            message="Missing or invalid Bearer authorization header",
        )

    token = authorization.split(" ")[1]
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if not username:
            raise AppException(status_code=401, code="UNAUTHORIZED", message="Token payload missing subject")
    except (jwt.PyJWTError, Exception) as exc:
        raise AppException(status_code=401, code="UNAUTHORIZED", message=f"Token verification failed: {exc}")

    user = db.scalar(select(User).where(User.username == username))
    if not user:
        raise AppException(status_code=401, code="UNAUTHORIZED", message="User account not found")

    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    """Dependency enforcing role-based access control."""

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Role '{user.role.value}' is not permitted to perform this action",
            )
        return user

    return role_checker


async def get_scope(
    request: Request,
    patient_id: str = Path(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Scope:
    """
    Hospital-Aware Patient Scope Validation:
    1. Patient exists (404).
    2. OVA_ADMIN has no clinical patient access (403).
    3. PATIENT can only access their own patient_id (403).
    4. For clinical roles (DOCTOR, HOSPITAL_ADMIN, STAFF, ADMIN):
       User's hospital must have an ACTIVE patient_hospital_access row (READ_ONLY or READ_WRITE) (403).
    5. DOCTOR also needs an active doctor_patient assignment (403).
    6. If cycle_id is given, validates existence and patient association (404).
    """
    cycle_id: Optional[str] = request.path_params.get("cycle_id") or request.query_params.get("cycle_id")

    # 1. Patient existence check
    patient = db.get(Patient, patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{patient_id}' not found",
        )

    # 2. OVA_ADMIN has no clinical patient chart access
    if user.role == UserRole.OVA_ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="OVA administrators do not have access to clinical patient charts.",
        )

    # 3. PATIENT can only access their own chart
    if user.role == UserRole.PATIENT:
        if not user.patient_id or user.patient_id != patient_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Patients are strictly restricted to accessing their own chart ({user.patient_id or 'none'}).",
            )
        return Scope(
            user=user,
            patient_id=patient_id,
            cycle_id=cycle_id,
            org_id=user.org_id,
            hospital_id=user.hospital_id or user.org_id,
            access_level=HospitalAccessLevel.READ_ONLY,
        )

    # 4. Hospital-aware active access check
    user_hospital_id = user.hospital_id or user.org_id
    pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == patient_id,
            PatientHospitalAccess.hospital_id == user_hospital_id,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if not pha:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hospital_id}' does not have active authorized access to patient '{patient_id}'",
        )

    access_level = pha.access_level

    # 5. DOCTOR also needs an assignment
    if user.role == UserRole.DOCTOR:
        assignment = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == user.id,
                DoctorPatient.patient_id == patient_id,
            )
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Doctor '{user.username}' is not assigned to patient '{patient_id}'",
            )

    # 6. Cycle check if cycle_id is provided
    if cycle_id:
        cycle = db.get(Cycle, cycle_id)
        if not cycle or cycle.patient_id != patient_id:
            raise AppException(
                status_code=404,
                code="NOT_FOUND",
                message=f"Cycle '{cycle_id}' not found for patient '{patient_id}'",
            )

    return Scope(
        user=user,
        patient_id=patient_id,
        cycle_id=cycle_id,
        org_id=user.org_id,
        hospital_id=user_hospital_id,
        access_level=access_level,
    )


def require_write_access(scope: Scope = Depends(get_scope)) -> Scope:
    """
    Enforces that:
    1. Scope is valid.
    2. Role is not PATIENT or OVA_ADMIN.
    3. User's hospital has READ_WRITE access to the patient.
    """
    if scope.user.role == UserRole.PATIENT:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Patients have read-only access and cannot perform modifications.",
        )
    if scope.user.role == UserRole.OVA_ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="OVA administrators cannot modify clinical records.",
        )
    if scope.access_level != HospitalAccessLevel.READ_WRITE:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{scope.hospital_id}' has {scope.access_level.value} access to patient '{scope.patient_id}'; action requires READ_WRITE access",
        )
    return scope
