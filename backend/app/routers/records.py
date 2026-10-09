from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.patient import Patient, DoctorPatient
from app.models.source_record import SourceRecord
from app.models.provenance import PatientHospitalAccess
from app.models.enums import UserRole, SourceProcessingStatus, HospitalAccessStatus
from app.models.user import User

from app.core.scope import require_roles
from app.core.audit import record_audit
from app.services.audit_service import AuditService, AuditEvent
from app.core.errors import AppException
from app.schemas.responses import SourceRecordDetailResponse
from app.schemas.source_record import RecordStatusResponse

router = APIRouter(prefix="/records", tags=["records"])


@router.get(
    "/{source_id}/status",
    response_model=RecordStatusResponse,
    summary="Get source record processing status",
    description="Check the processing status of a source document (UPLOADED, EXTRACTING, VALIDATED, NEEDS_OCR, FAILED).",
)
async def get_record_status(
    source_id: str,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN, UserRole.STAFF, UserRole.HOSPITAL_ADMIN, UserRole.OVA_ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieve document ingestion and text extraction status for a source record."""
    record = db.get(SourceRecord, source_id)
    if not record:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Source record with id '{source_id}' was not found",
        )

    patient = db.get(Patient, record.patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{record.patient_id}' not found",
        )

    # Scoping check: home org or active delegated access
    if patient.org_id != current_user.org_id:
        pha = db.scalar(
            select(PatientHospitalAccess).where(
                PatientHospitalAccess.patient_id == patient.id,
                PatientHospitalAccess.hospital_id == current_user.org_id,
                PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
            )
        )
        if not pha and current_user.role not in [UserRole.ADMIN, UserRole.OVA_ADMIN]:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message="Source record belongs to a patient in another organization",
            )

    if current_user.role == UserRole.DOCTOR:
        assignment = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == current_user.id,
                DoctorPatient.patient_id == record.patient_id,
            )
        )
        if not assignment:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message="Doctor is not assigned to the patient associated with this record",
            )

    warnings: list[str] = []
    if record.processing_status == SourceProcessingStatus.NEEDS_OCR:
        warnings.append("Document appears to be a scanned image or lacks an embedded text layer. OCR is required.")

    return RecordStatusResponse(
        id=record.id,
        patient_id=record.patient_id,
        processing_status=record.processing_status,
        mime_type=record.mime_type,
        content_hash=record.content_hash,
        type=record.type,
        date=record.date,
        author=record.author,
        origin_org=record.origin_org,
        warnings=warnings,
    )


@router.get(
    "/{source_id}",
    response_model=SourceRecordDetailResponse,
    summary="Get clinical source record",
    description="Retrieve original clinical document text and metadata with provenance. Access is restricted to authorized clinicians or patient self.",
)
async def get_source_record(
    source_id: str,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.PATIENT)),
    db: Session = Depends(get_db),
):
    """
    Retrieve full content and metadata of a source record.
    Verifies that the record belongs to a patient the user is authorized to access.
    """
    if current_user.role == UserRole.OVA_ADMIN:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="OVA administrators cannot access clinical source records.",
        )

    record = db.get(SourceRecord, source_id)
    if not record:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Source record with id '{source_id}' was not found",
        )

    patient = db.get(Patient, record.patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{record.patient_id}' not found",
        )

    if current_user.role == UserRole.PATIENT:
        if record.patient_id != current_user.patient_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message="Patients can only access their own records",
            )
    else:
        user_hosp = current_user.hospital_id or current_user.org_id
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
                message="Hospital does not have active access to patient records",
            )

        if current_user.role == UserRole.DOCTOR:
            assignment = (
                db.query(DoctorPatient)
                .filter(
                    DoctorPatient.doctor_id == current_user.id,
                    DoctorPatient.patient_id == record.patient_id,
                )
                .first()
            )
            if not assignment:
                raise AppException(
                    status_code=403,
                    code="FORBIDDEN",
                    message="Doctor is not assigned to the patient associated with this record",
                )

    AuditService.log_from_user(
        db, current_user, AuditEvent.RECORD_VIEWED,
        patient_id=record.patient_id,
        record_id=source_id,
    )

    return SourceRecordDetailResponse(
        id=record.id,
        patient_id=record.patient_id,
        cycle_id=record.cycle_id,
        type=record.type,
        date=record.date,
        author=record.author,
        origin_org=record.origin_org,
        trust_status=record.trust_status.value if hasattr(record.trust_status, "value") else str(record.trust_status),
        version=record.version,
        content_text=record.content_text,
        source_refs=[record.id],
    )
