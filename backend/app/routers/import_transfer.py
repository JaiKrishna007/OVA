from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.transfer import Consent, IdentityLink, ImportBatch
from app.models.provenance import TransferRequest
from app.schemas.transfer import (
    ImportUploadRequest,
    ImportBatchRead,
    ImportConfirmRequest,
    ConsentCreateRequest,
    ConsentRead,
    IdentityLinkRead,
)
from app.schemas.provenance import TransferRequestRead
from app.services.transfer_service import (
    create_quarantine_batch,
    confirm_import_batch,
    create_consent,
)
from app.core.scope import require_roles

router = APIRouter(tags=["transfer-import"])


@router.post(
    "/import",
    response_model=ImportBatchRead,
    status_code=201,
    summary="Upload external records into a quarantine batch (Staff only)",
)
def upload_import_batch(
    payload: ImportUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN)),
):
    """
    Staff-only endpoint: uploads external clinic payload into a quarantined batch.
    Performs structural validation, evaluates cross-clinic identity match confidence,
    and generates cycle assignment suggestions without altering the primary chart.
    """
    batch = create_quarantine_batch(db, current_user, payload)
    return batch


@router.get(
    "/import",
    response_model=List[ImportBatchRead],
    summary="List quarantined import batches (Staff only)",
)
def list_import_batches(
    status: Optional[str] = Query(None, description="Optional status filter (quarantined, confirmed, rejected)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN)),
):
    """Lists quarantined batches for review queue."""
    query = select(ImportBatch).where(ImportBatch.org_id == current_user.org_id)
    if status:
        query = query.where(ImportBatch.status == status)
    query = query.order_by(desc(ImportBatch.created_at))
    batches = db.scalars(query).all()
    return batches


@router.get(
    "/import/{batch_id}",
    response_model=ImportBatchRead,
    summary="Get import batch details (Staff only)",
)
def get_import_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN)),
):
    """
    Returns validation report, identity match confidence, and cycle assignment suggestions
    for the quarantine batch.
    """
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.org_id != current_user.org_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to batch from different org")
    return batch


@router.post(
    "/import/{batch_id}/confirm",
    response_model=ImportBatchRead,
    summary="Confirm and merge quarantine batch (Staff only)",
)
def confirm_batch(
    batch_id: str,
    confirm_req: ImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN)),
):
    """
    Confirms an import batch. Requires:
    - Active recorded patient transfer consent (409 Conflict if missing).
    - Confirmed identity link (strictly blocks auto-merging on name alone without confirmation).
    Commits records with origin_org and trust_status=external_unverified,
    and marks patient summary stale.
    """
    return confirm_import_batch(db, batch_id, current_user, confirm_req)




@router.get(
    "/transfer-requests",
    response_model=List[TransferRequestRead],
    summary="List hospital transfer requests",
)
def list_transfer_requests(
    patient_id: Optional[str] = Query(None, description="Optional patient ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN, UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.OVA_ADMIN, UserRole.PATIENT)),
):
    """Lists transfer requests for patient or hospital admin."""
    user_hosp = current_user.hospital_id or current_user.org_id
    if current_user.role == UserRole.PATIENT:
        query = select(TransferRequest).where(TransferRequest.patient_id == current_user.patient_id)
    elif current_user.role in (UserRole.ADMIN, UserRole.OVA_ADMIN):
        query = select(TransferRequest)
        if patient_id:
            query = query.where(TransferRequest.patient_id == patient_id)
    else:
        query = select(TransferRequest).where(
            (TransferRequest.from_hospital_id == user_hosp) | (TransferRequest.to_hospital_id == user_hosp)
        )
        if patient_id:
            query = query.where(TransferRequest.patient_id == patient_id)
    query = query.order_by(desc(TransferRequest.id))
    return db.scalars(query).all()


@router.get(
    "/identity-links",
    response_model=List[IdentityLinkRead],
    summary="List confirmed identity links",
)
def list_identity_links(
    patient_id: Optional[str] = Query(None, description="Optional internal patient ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN, UserRole.DOCTOR)),
):
    """Lists verified cross-clinic identity links."""
    query = select(IdentityLink)
    if patient_id:
        query = query.where(IdentityLink.internal_patient_id == patient_id)
    query = query.order_by(desc(IdentityLink.created_at))
    return db.scalars(query).all()
