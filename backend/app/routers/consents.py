from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.transfer import Consent
from app.schemas.transfer import ConsentCreateRequest, ConsentRead
from app.core.scope import require_roles, get_current_user
from app.services.transfer_service import create_consent, get_patient_consents, revoke_consent

router = APIRouter(tags=["consents"])


@router.post(
    "/consents",
    response_model=ConsentRead,
    status_code=201,
    summary="Grant or record patient transfer consent",
)
def record_consent_route(
    consent_in: ConsentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.STAFF,
        UserRole.DOCTOR,
        UserRole.OVA_ADMIN,
    )),
):
    """
    Grants consent to a target hospital with purpose (default: 'Continuity of fertility care'),
    scope (default: 'ALL_RECORDS'), and optional expiry.
    Can be recorded by patient or by hospital admin on the patient's behalf (flagged as such).
    """
    return create_consent(db, current_user, consent_in)


@router.get(
    "/patients/{id}/consents",
    response_model=List[ConsentRead],
    summary="Get patient consents",
)
def get_patient_consents_route(
    id: str = Path(..., description="Patient ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.STAFF,
        UserRole.DOCTOR,
        UserRole.OVA_ADMIN,
    )),
):
    """Retrieves all consents recorded for a patient, auto-evaluating expiration."""
    return get_patient_consents(db, current_user, id)


@router.get(
    "/consents",
    response_model=List[ConsentRead],
    summary="List recorded consents",
)
def list_consents_route(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.STAFF,
        UserRole.DOCTOR,
        UserRole.OVA_ADMIN,
    )),
):
    """Lists consents for patient or current hospital."""
    if patient_id:
        return get_patient_consents(db, current_user, patient_id)

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient_id:
            return []
        return get_patient_consents(db, current_user, current_user.patient_id)

    user_hosp = current_user.hospital_id or current_user.org_id
    if current_user.role in (UserRole.ADMIN, UserRole.OVA_ADMIN):
        query = select(Consent).order_by(desc(Consent.created_at))
    else:
        query = select(Consent).where(
            (Consent.org_id == user_hosp) | (Consent.granted_to_hospital_id == user_hosp)
        ).order_by(desc(Consent.created_at))
    return list(db.scalars(query).all())


@router.delete(
    "/consents/{id}",
    response_model=ConsentRead,
    summary="Revoke patient consent",
)
def revoke_consent_route(
    id: str = Path(..., description="Consent ID to revoke"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.STAFF,
        UserRole.DOCTOR,
        UserRole.OVA_ADMIN,
    )),
):
    """
    Revokes consent: status becomes REVOKED, and access of that hospital becomes
    REVOKED going forward. History is retained and audited.
    """
    return revoke_consent(db, current_user, id)
