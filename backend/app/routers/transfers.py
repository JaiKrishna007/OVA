from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, func, or_

from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.patient import Patient
from app.models.transfer import Consent
from app.models.provenance import TransferRequest
from app.schemas.transfer import TransferCreateRequest
from app.schemas.provenance import TransferRequestRead
from app.core.scope import require_roles
from app.services.transfer_service import (
    create_transfer_request,
    accept_transfer_request,
    reject_transfer_request,
    cancel_transfer_request,
    clear_all_transfers,
)
from app.core.errors import AppException

router = APIRouter(tags=["transfers"])


def _enrich_transfer(transfer: TransferRequest, db: Session) -> dict:
    patient = db.get(Patient, transfer.patient_id)
    now = datetime.now(timezone.utc)
    consents = list(db.scalars(
        select(Consent).where(
            Consent.patient_id == transfer.patient_id,
            func.upper(Consent.status) == "ACTIVE",
            or_(
                Consent.granted_to_hospital_id == transfer.to_hospital_id,
                Consent.org_id == transfer.to_hospital_id,
            ),
        )
    ).all())

    has_active_consent = False
    for c in consents:
        if c.expires_at:
            exp = c.expires_at if c.expires_at.tzinfo else c.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                continue
        has_active_consent = True
        break

    return {
        "id": transfer.id,
        "patient_id": transfer.patient_id,
        "patient_name": patient.name if patient else transfer.patient_id,
        "from_hospital_id": transfer.from_hospital_id,
        "to_hospital_id": transfer.to_hospital_id,
        "requested_by": transfer.requested_by,
        "status": transfer.status,
        "consent_id": transfer.consent_id or (consents[0].id if (consents and has_active_consent) else None),
        "has_active_consent": has_active_consent,
        "decided_by": transfer.decided_by,
        "decided_at": transfer.decided_at,
        "reason": transfer.reason,
        "created_at": transfer.created_at,
    }


class RejectPayload(BaseModel):
    reason: Optional[str] = None


@router.post(
    "/transfers",
    response_model=TransferRequestRead,
    status_code=201,
    summary="Request a patient hospital transfer",
)
def request_transfer_route(
    req: TransferCreateRequest,
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
    Creates a transfer request (status: REQUESTED) from sending hospital to receiving hospital.
    Can be initiated by the patient or current-hospital admin.
    """
    return _enrich_transfer(create_transfer_request(db, current_user, req), db)


@router.get(
    "/transfers",
    response_model=List[TransferRequestRead],
    summary="List hospital transfer requests",
)
def list_transfers_route(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    direction: Optional[str] = Query(None, description="'incoming' or 'outgoing'"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. REQUESTED, COMPLETED)"),
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
    Lists transfer requests with scoping:
    - Patient sees their own requests.
    - Clinicians & hospital admins see requests where their hospital is sender or receiver.
    - OVA Admin sees all requests.
    """
    user_hosp = current_user.hospital_id or current_user.org_id
    if current_user.role == UserRole.PATIENT:
        query = select(TransferRequest).where(TransferRequest.patient_id == current_user.patient_id)
    elif current_user.role in (UserRole.ADMIN, UserRole.OVA_ADMIN):
        query = select(TransferRequest)
    else:
        query = select(TransferRequest).where(
            (TransferRequest.from_hospital_id == user_hosp) | (TransferRequest.to_hospital_id == user_hosp)
        )

    if patient_id:
        query = query.where(TransferRequest.patient_id == patient_id)
    if direction == "incoming" and user_hosp:
        query = query.where(TransferRequest.to_hospital_id == user_hosp)
    elif direction == "outgoing" and user_hosp:
        query = query.where(TransferRequest.from_hospital_id == user_hosp)
    if status:
        query = query.where(TransferRequest.status == status.upper())

    query = query.order_by(desc(TransferRequest.id))
    return [_enrich_transfer(t, db) for t in db.scalars(query).all()]


@router.get(
    "/transfers/{id}",
    response_model=TransferRequestRead,
    summary="Get transfer request details",
)
def get_transfer_route(
    id: str = Path(..., description="Transfer request ID"),
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
    """Retrieves single transfer request details."""
    transfer = db.get(TransferRequest, id)
    if not transfer:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Transfer request '{id}' not found",
        )

    if current_user.role == UserRole.PATIENT and transfer.patient_id != current_user.patient_id:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Patients can only view their own transfer requests.",
        )

    user_hosp = current_user.hospital_id or current_user.org_id
    if current_user.role not in (UserRole.ADMIN, UserRole.OVA_ADMIN, UserRole.PATIENT):
        if transfer.from_hospital_id != user_hosp and transfer.to_hospital_id != user_hosp:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message="Unauthorized to view this transfer request.",
            )

    return _enrich_transfer(transfer, db)


@router.post(
    "/transfers/{id}/accept",
    response_model=TransferRequestRead,
    summary="Accept a transfer request",
)
def accept_transfer_route(
    id: str = Path(..., description="Transfer request ID to accept"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.OVA_ADMIN,
    )),
):
    """
    Patient or receiving hospital admin accepts transfer request:
    - Verifies an ACTIVE consent for the receiving hospital exists (otherwise 409 CONSENT_REQUIRED).
    - If patient confirms, consent is recorded under patient's authorization.
    - In one atomic transaction:
      - Sending hospital access becomes READ_ONLY.
      - Receiving hospital becomes READ_WRITE.
      - Transfer status is set to COMPLETED.
      - Patient summary is marked stale.
    - Records remain intact with immutable origin hospital.
    - Double accept is idempotent.
    """
    return _enrich_transfer(accept_transfer_request(db, current_user, id), db)


@router.post(
    "/transfers/{id}/reject",
    response_model=TransferRequestRead,
    summary="Reject or revoke a transfer request",
)
def reject_transfer_route(
    id: str = Path(..., description="Transfer request ID to reject"),
    payload: Optional[RejectPayload] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.OVA_ADMIN,
    )),
):
    """Patient or receiving hospital admin rejects/revokes the transfer request. Idempotent."""
    reason = payload.reason if payload else None
    return _enrich_transfer(reject_transfer_request(db, current_user, id, reason=reason), db)


@router.post(
    "/transfers/{id}/cancel",
    response_model=TransferRequestRead,
    summary="Cancel a transfer request",
)
def cancel_transfer_route(
    id: str = Path(..., description="Transfer request ID to cancel"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.PATIENT,
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.STAFF,
        UserRole.OVA_ADMIN,
    )),
):
    """Cancels a pending transfer request. Idempotent."""
    return _enrich_transfer(cancel_transfer_request(db, current_user, id), db)


@router.post(
    "/transfers/clear",
    summary="Clear all transfer data and reset to initial baseline",
)
def clear_transfers_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        UserRole.HOSPITAL_ADMIN,
        UserRole.ADMIN,
        UserRole.OVA_ADMIN,
        UserRole.DOCTOR,
    )),
):
    """
    Clears all transfer requests, removes transfer-granted accesses,
    and resets patient hospital access back to clean baseline.
    """
    return clear_all_transfers(db, current_user)
