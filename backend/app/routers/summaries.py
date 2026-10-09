import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.summary import Summary, SummaryFeedback
from app.models.patient import Patient, DoctorPatient
from app.models.user import User
from app.models.enums import UserRole
from app.core.scope import require_roles
from app.core.errors import AppException
from app.core.audit import record_audit
from app.schemas.summary import SummaryFeedbackRead

router = APIRouter(prefix="/summaries", tags=["summaries"])


class FeedbackCreateRequest(BaseModel):
    statement_ref: str = Field(..., max_length=100, description="Statement reference or claim ID", examples=["CLM-001"])
    type: str = Field("incorrect_fact", max_length=50, description="Feedback classification type", examples=["incorrect_fact"])
    comment: Optional[str] = Field(None, max_length=2000, description="Clinician observation or correction", examples=["Oocyte count in note conflicts with lab report"])


@router.post("/{summary_id}/feedback", response_model=SummaryFeedbackRead)
async def create_summary_feedback(
    summary_id: str,
    payload: FeedbackCreateRequest,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    db: Session = Depends(get_db),
):
    """Submit doctor feedback or flag an incorrect fact in an AI summary."""
    summary = db.get(Summary, summary_id)
    if not summary:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Summary '{summary_id}' not found",
        )

    patient = db.get(Patient, summary.patient_id)
    if not patient or patient.org_id != current_user.org_id:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Access to patient '{summary.patient_id}' is forbidden",
        )

    if current_user.role == UserRole.DOCTOR:
        assignment = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == current_user.id,
                DoctorPatient.patient_id == summary.patient_id,
            )
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Doctor '{current_user.username}' is not assigned to patient '{summary.patient_id}'",
            )

    fb = SummaryFeedback(
        id=f"FB-{uuid.uuid4().hex[:8]}",
        summary_id=summary.id,
        statement_ref=payload.statement_ref,
        type=payload.type,
        comment=payload.comment,
        user_id=current_user.id,
        at=datetime.now(timezone.utc),
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    record_audit(db, user_id=current_user.id, action="summary_feedback", patient_id=summary.patient_id)
    return fb
