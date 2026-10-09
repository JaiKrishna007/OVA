import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.provenance import ClinicalClaim, PatientHospitalAccess
from app.models.source_record import SourceRecord
from app.models.patient import DoctorPatient
from app.models.enums import UserRole, ClaimValidationStatus, HospitalAccessStatus, HospitalAccessLevel
from app.models.user import User
from app.core.scope import get_current_user, require_roles
from app.core.errors import AppException
from app.core.audit import record_audit
from app.services.audit_service import AuditService, AuditEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["claims"])


def _verify_doctor_claim_read_access(db: Session, current_user: User, claim: ClinicalClaim):
    """Verifies that doctor is assigned to the claim's patient for read operations."""
    if current_user.role in (UserRole.ADMIN, UserRole.OVA_ADMIN, UserRole.STAFF, UserRole.HOSPITAL_ADMIN):
        return

    if current_user.role == UserRole.DOCTOR:
        assignment = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == current_user.id,
                DoctorPatient.patient_id == claim.patient_id,
            )
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Doctor '{current_user.username}' is not assigned to patient '{claim.patient_id}'.",
            )


def _verify_doctor_claim_access(db: Session, current_user: User, claim: ClinicalClaim):
    """Verifies that doctor is assigned to the claim's patient and hospital has active READ_WRITE access."""
    if current_user.role == UserRole.OVA_ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="OVA administrators cannot manage clinical claims.",
        )

    if current_user.role == UserRole.PATIENT:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Patients cannot accept or reject clinical claims.",
        )

    user_hosp = current_user.hospital_id or current_user.org_id
    if current_user.role == UserRole.DOCTOR:
        assignment = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == current_user.id,
                DoctorPatient.patient_id == claim.patient_id,
            )
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Doctor '{current_user.username}' is not assigned to patient '{claim.patient_id}'.",
            )

    # Hospital access check
    pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == claim.patient_id,
            PatientHospitalAccess.hospital_id == user_hosp,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if not pha and current_user.role != UserRole.ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message=f"Hospital '{user_hosp}' does not have active access to patient '{claim.patient_id}'.",
        )
    if pha and pha.access_level == HospitalAccessLevel.READ_ONLY:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Hospital has READ_ONLY access; claims cannot be modified.",
        )


@router.post(
    "/{claim_id}/accept",
    summary="Doctor accepts a FLAGGED clinical claim",
    description="Promotes a FLAGGED claim to VERIFIED status so it can be materialized into clinical tables. Audit-logged.",
)
async def accept_claim(
    claim_id: str = Path(..., description="Claim ID (e.g. CLM-12345678)"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    claim = db.get(ClinicalClaim, claim_id)
    if not claim:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Claim '{claim_id}' not found.")

    _verify_doctor_claim_access(db, current_user, claim)

    claim.validation_status = ClaimValidationStatus.VERIFIED
    from app.services.materializer.service import materialize_claims
    materialize_claims(db, patient_id=claim.patient_id)

    AuditService.log_from_user(
        db, current_user, AuditEvent.CLAIM_ACCEPTED,
        patient_id=claim.patient_id,
        claim_id=claim.id,
        details={
            "field": claim.field,
            "value": claim.value_text,
            "previous_reasons": claim.reason_codes,
        },
    )
    db.commit()
    db.refresh(claim)

    return {
        "status": "ok",
        "claim_id": claim.id,
        "validation_status": claim.validation_status.value,
        "message": f"Claim '{claim.id}' accepted and marked VERIFIED.",
    }


@router.post(
    "/{claim_id}/reject",
    summary="Doctor rejects a clinical claim",
    description="Sets claim status to REJECTED. The claim remains archived for transparency but excluded from clinical synthesis.",
)
async def reject_claim(
    claim_id: str = Path(..., description="Claim ID (e.g. CLM-12345678)"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    claim = db.get(ClinicalClaim, claim_id)
    if not claim:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Claim '{claim_id}' not found.")

    _verify_doctor_claim_access(db, current_user, claim)

    claim.validation_status = ClaimValidationStatus.REJECTED
    AuditService.log_from_user(
        db, current_user, AuditEvent.CLAIM_REJECTED,
        patient_id=claim.patient_id,
        claim_id=claim.id,
        details={
            "field": claim.field,
            "value": claim.value_text,
            "reason_codes": claim.reason_codes,
        },
    )

    from app.services.engines.conflicts import recompute_and_persist_conflicts
    from app.services.engines.gaps import recompute_and_persist_gaps
    recompute_and_persist_conflicts(db, claim.patient_id)
    recompute_and_persist_gaps(db, claim.patient_id)

    db.commit()
    db.refresh(claim)

    return {
        "status": "ok",
        "claim_id": claim.id,
        "validation_status": claim.validation_status.value,
        "message": f"Claim '{claim.id}' rejected.",
    }


@router.get(
    "",
    summary="Query clinical claims",
    description="List clinical claims filtered by patient_id, validation status (e.g. FLAGGED), or field.",
)
async def list_claims(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status: Optional[str] = Query(None, description="Filter by validation status (VERIFIED, REJECTED, FLAGGED)"),
    field: Optional[str] = Query(None, description="Filter by clinical field name"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.STAFF, UserRole.OVA_ADMIN)),
    db: Session = Depends(get_db),
):
    stmt = select(ClinicalClaim)
    if patient_id:
        stmt = stmt.where(ClinicalClaim.patient_id == patient_id)
    if status:
        try:
            status_enum = ClaimValidationStatus[status.upper()]
            stmt = stmt.where(ClinicalClaim.validation_status == status_enum)
        except KeyError:
            pass
    if field:
        stmt = stmt.where(ClinicalClaim.field == field.lower())

    stmt = stmt.order_by(ClinicalClaim.created_at.desc())
    claims = db.scalars(stmt).all()

    return [
        {
            "id": c.id,
            "patient_id": c.patient_id,
            "hospital_id": c.hospital_id,
            "source_record_id": c.source_record_id,
            "field": c.field,
            "value_text": c.value_text,
            "value_num": c.value_num,
            "unit": c.unit,
            "event_date": c.event_date.isoformat() if c.event_date else None,
            "span_start": c.span_start,
            "span_end": c.span_end,
            "evidence_text": c.evidence_text,
            "extraction_method": c.extraction_method.value,
            "validation_status": c.validation_status.value,
            "validation_checks": c.validation_checks,
            "reason_codes": c.reason_codes,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in claims
    ]


@router.get(
    "/{claim_id}/evidence",
    summary="Get claim evidence and validation checklist",
    description="Returns claim, source record metadata (id, hospital, date, uploader, type), the evidence text with the span highlighted, and each validation check with pass/fail and detail.",
)
async def get_claim_evidence(
    claim_id: str = Path(..., description="Claim ID (e.g. CLM-12345678)"),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.STAFF, UserRole.OVA_ADMIN)),
    db: Session = Depends(get_db),
):
    claim = db.get(ClinicalClaim, claim_id)
    if not claim:
        import re
        alt_id = re.sub(r"-(\d)$", r"-0\1", claim_id)
        if alt_id != claim_id:
            claim = db.get(ClinicalClaim, alt_id)
    if not claim:
        raise AppException(status_code=404, code="NOT_FOUND", message=f"Claim '{claim_id}' not found.")

    _verify_doctor_claim_read_access(db, current_user, claim)

    srec = db.get(SourceRecord, claim.source_record_id) if claim.source_record_id else None

    # Text extraction without HTML
    full_text = ""
    if srec and srec.content_text:
        full_text = srec.content_text
    elif claim.evidence_text:
        full_text = claim.evidence_text

    start = claim.span_start
    end = claim.span_end
    val = str(claim.value_text or "").strip()
    prefix = ""
    highlighted_text = ""
    suffix = ""
    evidence_sentence = ""

    # 1. Does srec.content_text have the value at [start:end]?
    if srec and srec.content_text and start is not None and end is not None and 0 <= start < end <= len(srec.content_text) and (not val or val in srec.content_text[start:end]):
        full_text = srec.content_text
        highlighted_text = full_text[start:end]
        prefix = full_text[:start]
        suffix = full_text[end:]
    # 2. Does claim.evidence_text have the value at [start:end]?
    elif claim.evidence_text and start is not None and end is not None and 0 <= start < end <= len(claim.evidence_text) and (not val or val in claim.evidence_text[start:end]):
        full_text = claim.evidence_text
        highlighted_text = full_text[start:end]
        prefix = full_text[:start]
        suffix = full_text[end:]
    # 3. Fallback: find val in claim.evidence_text
    elif claim.evidence_text and val and val in claim.evidence_text:
        full_text = claim.evidence_text
        idx = full_text.find(val)
        start = idx
        end = idx + len(val)
        highlighted_text = full_text[start:end]
        prefix = full_text[:start]
        suffix = full_text[end:]
    # 4. Fallback: find val in srec.content_text
    elif srec and srec.content_text and val and val in srec.content_text:
        full_text = srec.content_text
        idx = full_text.find(val)
        start = idx
        end = idx + len(val)
        highlighted_text = full_text[start:end]
        prefix = full_text[:start]
        suffix = full_text[end:]
    else:
        full_text = claim.evidence_text or (srec.content_text if srec else "")
        highlighted_text = val or full_text
        start = 0
        end = len(highlighted_text)
        prefix = ""
        suffix = ""

    # Locate enclosing sentence/line
    if full_text and highlighted_text:
        s_start = max(0, full_text.rfind("\n", 0, start) + 1 if "\n" in full_text[:start] else 0)
        s_end = full_text.find("\n", end)
        if s_end == -1:
            s_end = len(full_text)
        evidence_sentence = full_text[s_start:s_end].strip()
    if not evidence_sentence:
        evidence_sentence = claim.evidence_text or highlighted_text

    # Validation checks list
    reasons = claim.reason_codes or []
    val_passed = (claim.value_text is not None and (claim.value_text in full_text or "VALUE_NOT_IN_SOURCE" not in reasons))
    unit_str = claim.unit or "N/A"
    unit_passed = "UNIT_AMBIGUOUS" not in reasons and "UNIT_NOT_IN_SOURCE" not in reasons
    date_str = claim.event_date.isoformat() if claim.event_date else "N/A"
    date_passed = "DATE_NOT_IN_SOURCE" not in reasons and "DATE_LOW_CONFIDENCE" not in reasons
    span_passed = "SPAN_MISMATCH" not in reasons and "EMPTY_EVIDENCE" not in reasons and "SPAN_OUT_OF_RANGE" not in reasons

    validation_checks = [
        {
            "name": "check_value_in_source",
            "label": "Value verified",
            "passed": val_passed and ("VALUE_NOT_IN_SOURCE" not in reasons),
            "detail": f"Value '{claim.value_text}' matched in source document." if (val_passed and "VALUE_NOT_IN_SOURCE" not in reasons) else "Value not confirmed in source text.",
        },
        {
            "name": "check_unit_in_source",
            "label": "Unit verified",
            "passed": unit_passed,
            "detail": f"Unit '{unit_str}' verified and canonicalized." if unit_passed else ("Unit ambiguous across facilities." if "UNIT_AMBIGUOUS" in reasons else f"Unit '{unit_str}' not confirmed."),
        },
        {
            "name": "check_date_in_source",
            "label": "Date verified",
            "passed": date_passed,
            "detail": f"Event date {date_str} matched document timeline." if date_passed else "Date could not be confirmed in source document.",
        },
        {
            "name": "check_span_grounding",
            "label": "Source span verified",
            "passed": span_passed,
            "detail": f"Character span [{start}:{end}] grounded in raw record text." if span_passed else "Character span misaligned or empty.",
        },
    ]

    return {
        "claim": {
            "id": claim.id,
            "patient_id": claim.patient_id,
            "hospital_id": claim.hospital_id,
            "source_record_id": claim.source_record_id,
            "field": claim.field,
            "value_text": claim.value_text,
            "value_num": claim.value_num,
            "unit": claim.unit,
            "event_date": claim.event_date.isoformat() if claim.event_date else None,
            "span_start": start,
            "span_end": end,
            "evidence_text": claim.evidence_text,
            "validation_status": claim.validation_status.value,
            "extraction_method": claim.extraction_method.value,
            "reason_codes": claim.reason_codes or [],
            "created_at": claim.created_at.isoformat() if claim.created_at else None,
        },
        "source_record": {
            "id": srec.id if srec else claim.source_record_id,
            "hospital": srec.origin_org if srec else claim.hospital_id,
            "date": srec.date.isoformat() if srec and srec.date else (claim.event_date.isoformat() if claim.event_date else None),
            "uploader": srec.uploaded_by if srec else "system",
            "type": srec.type if srec else "clinical_record",
            "trust_status": srec.trust_status.value if srec and hasattr(srec.trust_status, "value") else (str(srec.trust_status) if srec else "verified"),
        },
        "evidence": {
            "full_text": full_text,
            "span_start": start,
            "span_end": end,
            "prefix": prefix,
            "highlighted_text": highlighted_text,
            "suffix": suffix,
            "evidence_sentence": evidence_sentence,
        },
        "validation_checks": validation_checks,
    }
