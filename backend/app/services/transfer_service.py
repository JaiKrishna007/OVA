import uuid
import re
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, func, or_

from app.models.enums import TrustStatus, CycleType, TransferRequestStatus, HospitalAccessLevel, HospitalAccessStatus, UserRole
from app.models.user import User
from app.models.patient import Patient, DoctorPatient
from app.models.cycle import Cycle
from app.models.source_record import SourceRecord
from app.models.summary import Summary
from app.models.transfer import Consent, IdentityLink, ImportBatch
from app.models.provenance import TransferRequest, PatientHospitalAccess
from app.models.clinical import TreatmentEvent, Investigation
from app.schemas.transfer import ImportUploadRequest, ImportConfirmRequest, ConsentCreateRequest, TransferCreateRequest
from app.core.audit import record_audit
from app.core.errors import AppException


def _clean_str(s: Optional[str]) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", s or "").lower()


def _parse_date(d_val: Any) -> Optional[date]:
    if isinstance(d_val, date):
        return d_val
    if isinstance(d_val, str) and d_val.strip():
        try:
            return datetime.strptime(d_val.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def evaluate_identity_match(
    internal_patient: Patient,
    ext_patient: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluates cross-clinic identity match criteria:
    - Never auto-merge on name alone.
    - High confidence (0.90+) requires DOB + Phone or DOB + exact Name.
    - Medium confidence (0.60-0.89) requires explicit staff confirmation.
    - Low confidence (name match alone) strictly blocks auto-merging.
    """
    int_name = _clean_str(internal_patient.name)
    ext_name = _clean_str(ext_patient.get("name"))

    int_dob = str(internal_patient.dob or "")
    ext_dob = str(ext_patient.get("dob") or "")

    int_phone = _clean_str(internal_patient.phone)
    ext_phone = _clean_str(ext_patient.get("phone"))

    name_match = (int_name == ext_name) or (int_name in ext_name) or (ext_name in int_name)
    dob_match = bool(int_dob and ext_dob and int_dob == ext_dob)

    # Phone matching: match last 5 digits or full cleaned digits
    phone_match = False
    if int_phone and ext_phone:
        if int_phone == ext_phone or int_phone[-5:] == ext_phone[-5:]:
            phone_match = True

    criteria = {
        "name_match": name_match,
        "dob_match": dob_match,
        "phone_match": phone_match,
    }

    # Scoring logic
    if dob_match and phone_match and name_match:
        score = 0.98
        confidence = "high"
        needs_staff_confirmation = False
        notes = "Exact DOB, phone, and name match."
    elif dob_match and phone_match:
        score = 0.90
        confidence = "high"
        needs_staff_confirmation = False
        notes = "DOB and phone match confirmed."
    elif dob_match and name_match:
        score = 0.75
        confidence = "medium"
        needs_staff_confirmation = True
        notes = "DOB and name match; phone unverified. Staff confirmation required."
    elif name_match:
        score = 0.45
        confidence = "low"
        needs_staff_confirmation = True
        notes = "Name match alone. High false-positive risk. Never auto-merge on name alone."
    else:
        score = 0.0
        confidence = "none"
        needs_staff_confirmation = True
        notes = "No matching demographic identifiers."

    return {
        "patient_id": internal_patient.id,
        "patient_name": internal_patient.name,
        "score": score,
        "confidence": confidence,
        "criteria": criteria,
        "needs_staff_confirmation": needs_staff_confirmation,
        "notes": notes,
    }


def create_quarantine_batch(
    db: Session,
    user: User,
    payload: ImportUploadRequest,
) -> ImportBatch:
    """
    Validates uploaded external transfer payload, computes identity-matching confidence,
    generates cycle-assignment suggestions, and saves to quarantine store.
    """
    batch_id = f"BAT-{uuid.uuid4().hex[:8].upper()}"
    p_dict = payload.patient.model_dump()

    # Find candidate patients
    patients = db.scalars(select(Patient).where(Patient.org_id == user.org_id)).all()
    if not patients:
        patients = db.scalars(select(Patient)).all()

    candidates = []
    for p in patients:
        res = evaluate_identity_match(p, p_dict)
        if res["score"] > 0.3:
            candidates.append(res)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best_match = candidates[0] if candidates else None

    # Structural validation report
    val_report = {
        "records_count": len(payload.records),
        "cycles_count": len(payload.cycles or []),
        "treatment_events_count": len(payload.treatment_events or []),
        "investigations_count": len(payload.investigations or []),
        "syntax_valid": True,
        "warnings": [],
    }
    if not payload.records and not payload.cycles:
        val_report["warnings"].append("Batch contains zero records and zero cycles.")

    # Cycle assignment suggestions
    cycle_suggestions = []
    for idx, c in enumerate(payload.cycles or [], 1):
        cycle_suggestions.append({
            "external_cycle_index": idx,
            "type": c.get("type", "IVF"),
            "start_date": c.get("start_date"),
            "suggested_action": "append_as_prior_external_cycle",
            "origin_org": payload.origin_org,
            "trust_status": TrustStatus.EXTERNAL_UNVERIFIED.value,
        })

    batch = ImportBatch(
        id=batch_id,
        uploaded_by=user.id,
        org_id=user.org_id,
        origin_org=payload.origin_org,
        status="quarantined",
        raw_payload_json=payload.model_dump(),
        validation_report_json=val_report,
        identity_match_json={
            "best_match": best_match,
            "candidates": candidates,
        },
        cycle_suggestions_json=cycle_suggestions,
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    record_audit(db, user_id=user.id, action="UPLOAD_IMPORT_BATCH", patient_id=best_match["patient_id"] if best_match else None, org_id=user.org_id)
    return batch


def confirm_import_batch(
    db: Session,
    batch_id: str,
    user: User,
    confirm_req: ImportConfirmRequest,
) -> ImportBatch:
    """
    Confirms an import batch:
    - Enforces recorded patient consent (409 Conflict if missing).
    - Blocks wrong-merge / name-only merges unless confirmed with verified criteria.
    - Commits records with origin_org and trust_status=external_unverified.
    - Marks patient summary stale.
    - Records confirmed identity link and audit log.
    """
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")

    if batch.status != "quarantined":
        raise HTTPException(status_code=400, detail=f"Batch is already {batch.status}")

    target_patient_id = confirm_req.target_patient_id
    patient = db.get(Patient, target_patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Target patient not found")

    # 1. Enforce Recorded Consent Check (Safety Rule)
    active_consent = db.scalars(
        select(Consent).where(
            Consent.patient_id == target_patient_id,
            Consent.status.in_(["active", "ACTIVE"]),
        )
    ).first()

    if not active_consent:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CONSENT_REQUIRED",
                "message": f"Active transfer consent is missing for patient {target_patient_id}. A recorded patient consent is strictly required before external records can be merged.",
            },
        )

    # 2. Wrong-Merge Prevention: Never auto-merge on name alone
    id_match = batch.identity_match_json or {}
    candidates = id_match.get("candidates", [])
    matched_entry = next((c for c in candidates if c["patient_id"] == target_patient_id), None)

    if matched_entry:
        if matched_entry.get("needs_staff_confirmation") and not confirm_req.confirm_identity:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "IDENTITY_CONFIRMATION_REQUIRED",
                    "message": "Cannot auto-merge on name alone. Demographic criteria require explicit staff confirmation.",
                },
            )
    else:
        # Patient was not in candidate list at all
        if not confirm_req.confirm_identity:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "UNMATCHED_IDENTITY",
                    "message": "Target patient did not meet demographic matching criteria. Explicit staff confirmation required.",
                },
            )

    # 3. Create IdentityLink record
    link_id = f"IDL-{uuid.uuid4().hex[:8].upper()}"
    p_data = batch.raw_payload_json.get("patient", {})
    link = IdentityLink(
        id=link_id,
        internal_patient_id=target_patient_id,
        external_patient_id=p_data.get("external_id") or "EXT-UNKNOWN",
        external_org_name=batch.origin_org,
        confidence_score=matched_entry.get("score", 0.5) if matched_entry else 0.5,
        match_criteria_json=matched_entry.get("criteria", {}) if matched_entry else {},
        status="confirmed",
        confirmed_by=user.id,
        confirmed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(link)

    # 4. Commit records with origin_org and trust_status=external_unverified
    raw = batch.raw_payload_json or {}
    created_rec_ids = []

    # Insert SourceRecords
    for rec_in in raw.get("records", []):
        rec_id = f"REC-EXT-{uuid.uuid4().hex[:6].upper()}"
        sr_date = _parse_date(rec_in.get("date")) or datetime.now(timezone.utc).date()
        sr = SourceRecord(
            id=rec_id,
            patient_id=target_patient_id,
            type=rec_in.get("type", "external_summary"),
            date=sr_date,
            author=rec_in.get("author", "External Physician"),
            origin_org=batch.origin_org,
            trust_status=TrustStatus.EXTERNAL_UNVERIFIED,
            content_text=rec_in.get("content_text", ""),
            version=1,
        )
        db.add(sr)
        created_rec_ids.append(rec_id)

    primary_source_id = created_rec_ids[0] if created_rec_ids else "REC-UNKNOWN"

    # Insert Cycles if present
    for cyc_in in raw.get("cycles", []):
        cyc_id = f"CY-EXT-{uuid.uuid4().hex[:6].upper()}"
        start_date = _parse_date(cyc_in.get("start_date")) or datetime.now(timezone.utc).date()
        end_date = _parse_date(cyc_in.get("end_date"))
        
        # Match CycleType enum
        raw_type = str(cyc_in.get("type", "IVF")).upper()
        cycle_type = CycleType.IVF
        for ct in CycleType:
            if ct.value.upper() == raw_type or ct.name.upper() == raw_type:
                cycle_type = ct
                break

        new_cycle = Cycle(
            id=cyc_id,
            patient_id=target_patient_id,
            org_id=user.org_id,
            cycle_no=cyc_in.get("cycle_no", 99),
            type=cycle_type,
            start_date=start_date,
            end_date=end_date,
            outcome=cyc_in.get("outcome"),
            origin_org=batch.origin_org,
            trust_status=TrustStatus.EXTERNAL_UNVERIFIED,
            source_id=primary_source_id,
        )
        db.add(new_cycle)

    # 5. Mark Patient Summary Stale
    summaries = db.scalars(select(Summary).where(Summary.patient_id == target_patient_id)).all()
    for s in summaries:
        if isinstance(s.content_json, dict):
            content = dict(s.content_json)
            content["is_stale"] = True
            s.content_json = content
        db.add(s)

    # 6. Update Batch
    batch.status = "confirmed"
    batch.target_patient_id = target_patient_id
    batch.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)

    # 7. Audit Log
    record_audit(
        db,
        user_id=user.id,
        action="CONFIRM_IMPORT",
        patient_id=target_patient_id,
        org_id=user.org_id,
    )

    return batch


def create_consent(
    db: Session,
    user: User,
    consent_in: ConsentCreateRequest,
) -> Consent:
    """
    Grants a consent to a target hospital.
    Can be recorded by patient directly or by hospital admin on patient's behalf (flagged as such).
    """
    patient = db.get(Patient, consent_in.patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{consent_in.patient_id}' not found",
        )

    recorded_on_behalf = consent_in.recorded_on_behalf
    if user.role == UserRole.PATIENT:
        if user.patient_id != consent_in.patient_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Patients can only record consent for their own medical records ({user.patient_id}).",
            )
        granted_by = consent_in.granted_by or user.username or "Patient"
        recorded_on_behalf = False
    elif user.role in (UserRole.HOSPITAL_ADMIN, UserRole.ADMIN, UserRole.STAFF, UserRole.DOCTOR):
        recorded_on_behalf = True
        granted_by = consent_in.granted_by or f"Hospital Admin ({user.username}) on behalf of patient"
    elif user.role == UserRole.OVA_ADMIN:
        recorded_on_behalf = True
        granted_by = f"OVA Admin ({user.username}) on behalf of patient"
    else:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Unauthorized to record consent.",
        )

    target_hosp = consent_in.target_hospital_id or consent_in.granted_to_hospital_id or user.hospital_id or user.org_id
    status_str = (consent_in.status or "ACTIVE").upper()

    consent_id = f"CNS-{uuid.uuid4().hex[:8].upper()}"
    consent = Consent(
        id=consent_id,
        patient_id=consent_in.patient_id,
        org_id=user.hospital_id or user.org_id,
        granted_to_hospital_id=target_hosp,
        purpose=consent_in.purpose or "Continuity of fertility care",
        scope=consent_in.scope or "ALL_RECORDS",
        consent_type=consent_in.consent_type or "external_transfer",
        status=status_str,
        granted_at=datetime.now(timezone.utc),
        expires_at=consent_in.expires_at,
        revoked_at=None,
        granted_by=granted_by,
        recorded_on_behalf=recorded_on_behalf,
        created_at=datetime.now(timezone.utc),
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    record_audit(
        db,
        user_id=user.id,
        action="RECORD_CONSENT",
        patient_id=consent_in.patient_id,
        org_id=user.hospital_id or user.org_id,
    )
    return consent


def get_patient_consents(
    db: Session,
    user: User,
    patient_id: str,
) -> List[Consent]:
    """Retrieves all consents for a patient, auto-evaluating expiration."""
    if user.role == UserRole.PATIENT and user.patient_id != patient_id:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Patients can only view their own consents.",
        )

    query = select(Consent).where(Consent.patient_id == patient_id).order_by(desc(Consent.created_at))
    consents = list(db.scalars(query).all())

    now = datetime.now(timezone.utc)
    dirty = False
    for c in consents:
        if c.status == "ACTIVE" and c.expires_at:
            exp = c.expires_at if c.expires_at.tzinfo else c.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                c.status = "EXPIRED"
                dirty = True
                db.add(c)
    if dirty:
        db.commit()

    return consents


def revoke_consent(
    db: Session,
    user: User,
    consent_id: str,
) -> Consent:
    """
    Revokes patient consent: status becomes REVOKED,
    and access of that hospital becomes REVOKED going forward.
    History retained and audited. Idempotent if already revoked.
    """
    consent = db.get(Consent, consent_id)
    if not consent:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Consent '{consent_id}' not found",
        )

    if user.role == UserRole.PATIENT and user.patient_id != consent.patient_id:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Patients can only revoke their own consent.",
        )

    if consent.status == "REVOKED":
        return consent

    now = datetime.now(timezone.utc)
    consent.status = "REVOKED"
    consent.revoked_at = now
    db.add(consent)

    # Access of that hospital becomes REVOKED going forward
    target_hosp = consent.granted_to_hospital_id or consent.org_id
    if target_hosp:
        access_rows = db.scalars(
            select(PatientHospitalAccess).where(
                PatientHospitalAccess.patient_id == consent.patient_id,
                PatientHospitalAccess.hospital_id == target_hosp,
            )
        ).all()
        for pha in access_rows:
            pha.status = HospitalAccessStatus.REVOKED
            db.add(pha)

    record_audit(
        db,
        user_id=user.id,
        action="REVOKE_CONSENT",
        patient_id=consent.patient_id,
        org_id=user.hospital_id or user.org_id,
    )
    db.commit()
    db.refresh(consent)
    return consent


def create_transfer_request(
    db: Session,
    user: User,
    req: TransferCreateRequest,
) -> TransferRequest:
    """
    Initiates a hospital transfer request (REQUESTED status).
    Can be created by the patient or current-hospital admin.
    """
    patient = db.get(Patient, req.patient_id)
    if not patient:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Patient '{req.patient_id}' not found",
        )

    if user.role == UserRole.PATIENT:
        if user.patient_id != req.patient_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Patients can only request transfers for their own chart ({user.patient_id}).",
            )
        if req.from_hospital_id:
            from_hosp = req.from_hospital_id
        else:
            pha = db.scalar(
                select(PatientHospitalAccess).where(
                    PatientHospitalAccess.patient_id == req.patient_id,
                    PatientHospitalAccess.access_level == HospitalAccessLevel.READ_WRITE,
                    PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
                )
            )
            from_hosp = pha.hospital_id if pha else patient.org_id
    else:
        user_hosp = user.hospital_id or user.org_id
        from_hosp = req.from_hospital_id or user_hosp
        if user.role not in (UserRole.ADMIN, UserRole.OVA_ADMIN) and from_hosp != user_hosp:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Hospital admins can only initiate transfers from their own facility ({user_hosp}).",
            )

    if from_hosp == req.to_hospital_id:
        raise AppException(
            status_code=400,
            code="BAD_REQUEST",
            message="Sending and receiving hospitals cannot be the same.",
        )

    # Invariant: Do not allow duplicate transfer requests
    # 1. Check for any existing pending transfer for this patient
    existing_pending = db.scalar(
        select(TransferRequest).where(
            TransferRequest.patient_id == req.patient_id,
            TransferRequest.status == TransferRequestStatus.REQUESTED,
        )
    )
    if existing_pending:
        raise AppException(
            status_code=409,
            code="DUPLICATE_TRANSFER",
            message=f"A transfer request for patient '{req.patient_id}' is already pending ({existing_pending.id} to {existing_pending.to_hospital_id}). Duplicate or concurrent transfer requests are not permitted.",
        )

    # 2. Check if patient already has active clinical care access at destination hospital
    dest_access = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == req.patient_id,
            PatientHospitalAccess.hospital_id == req.to_hospital_id,
            PatientHospitalAccess.access_level == HospitalAccessLevel.READ_WRITE,
            PatientHospitalAccess.status == HospitalAccessStatus.ACTIVE,
        )
    )
    if dest_access:
        raise AppException(
            status_code=409,
            code="DUPLICATE_TRANSFER",
            message=f"Patient '{req.patient_id}' already has active clinical care access at destination hospital '{req.to_hospital_id}'. Duplicate transfer is not permitted.",
        )

    transfer_id = f"TRF-{uuid.uuid4().hex[:8].upper()}"
    transfer = TransferRequest(
        id=transfer_id,
        patient_id=req.patient_id,
        from_hospital_id=from_hosp,
        to_hospital_id=req.to_hospital_id,
        requested_by=user.id,
        status=TransferRequestStatus.REQUESTED,
        reason=req.reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    record_audit(
        db,
        user_id=user.id,
        action="REQUEST_TRANSFER",
        patient_id=req.patient_id,
        org_id=from_hosp,
    )
    return transfer


def clear_all_transfers(db: Session, user: User) -> dict:
    """
    Clears all transfer data and restores initial clean hospital access baseline:
    - Deletes all records from transfer_requests.
    - Removes transfer-created secondary PatientHospitalAccess records.
    - Resets home PatientHospitalAccess records back to READ_WRITE and ACTIVE.
    - Resets delegate PatientHospitalAccess records back to READ_ONLY and ACTIVE.
    - Cleans up non-baseline consents.
    - Restores default doctor-patient assignments.
    """
    deleted_transfers = db.query(TransferRequest).delete()

    db.query(PatientHospitalAccess).filter(
        PatientHospitalAccess.source_transfer_id.isnot(None)
    ).delete(synchronize_session=False)

    home_phas = db.scalars(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.id.like("PHA-HOME-%")
        )
    ).all()
    for pha in home_phas:
        pha.access_level = HospitalAccessLevel.READ_WRITE
        pha.status = HospitalAccessStatus.ACTIVE
        pha.source_transfer_id = None

    delegates = db.scalars(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.id.like("PHA-DELEGATE-%")
        )
    ).all()
    for d in delegates:
        d.access_level = HospitalAccessLevel.READ_ONLY
        d.status = HospitalAccessStatus.ACTIVE
        d.source_transfer_id = None

    # Keep only baseline seed consent CNS-P105-01
    db.query(Consent).filter(Consent.id != "CNS-P105-01").delete(synchronize_session=False)

    # Restore default doctor assignments
    db.query(DoctorPatient).delete()
    db.add(DoctorPatient(doctor_id="USR-RAO", patient_id="P-101"))
    db.add(DoctorPatient(doctor_id="USR-RAO", patient_id="P-102"))
    db.add(DoctorPatient(doctor_id="USR-RAO", patient_id="P-103"))
    db.add(DoctorPatient(doctor_id="USR-RAO", patient_id="P-104"))
    db.add(DoctorPatient(doctor_id="USR-RAO", patient_id="P-105"))
    db.add(DoctorPatient(doctor_id="USR-MENON", patient_id="P-105"))

    db.commit()

    record_audit(
        db,
        user_id=user.id,
        action="CLEAR_ALL_TRANSFERS",
        org_id=user.hospital_id or user.org_id,
    )

    return {
        "status": "success",
        "cleared_transfers_count": deleted_transfers,
        "message": "All transfer data cleared and clinical access permissions reset to baseline.",
    }


def accept_transfer_request(
    db: Session,
    user: User,
    transfer_id: str,
) -> TransferRequest:
    """
    Accepts transfer request in one transaction:
    - Verifies an ACTIVE consent for the receiving hospital exists (otherwise 409 CONSENT_REQUIRED).
    - Sending hospital access becomes READ_ONLY.
    - Receiving hospital access becomes READ_WRITE (ACTIVE).
    - Transfer status is set to COMPLETED.
    - Patient summary is marked stale.
    - Records remain intact with immutable origin hospital.
    - Idempotent on double accept.
    """
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Transfer request '{transfer_id}' not found",
        )

    # Double accept idempotency: return 200 with completed transfer without error
    if transfer.status == TransferRequestStatus.COMPLETED:
        return transfer

    if transfer.status in (TransferRequestStatus.REJECTED, TransferRequestStatus.CANCELLED):
        raise AppException(
            status_code=400,
            code="INVALID_STATE",
            message=f"Transfer request is {transfer.status.value} and cannot be accepted.",
        )

    if user.role == UserRole.PATIENT:
        if user.patient_id != transfer.patient_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Patients can only accept transfers for their own medical records ({user.patient_id}).",
            )
    elif user.role not in (UserRole.ADMIN, UserRole.OVA_ADMIN):
        user_hosp = user.hospital_id or user.org_id
        if user_hosp != transfer.to_hospital_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Only administrators of receiving hospital '{transfer.to_hospital_id}' or the patient can accept this transfer request.",
            )

    now = datetime.now(timezone.utc)

    # Verify ACTIVE consent for the receiving hospital exists
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

    active_consent = None
    for c in consents:
        if c.expires_at:
            exp = c.expires_at if c.expires_at.tzinfo else c.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                c.status = "EXPIRED"
                db.add(c)
                continue
        active_consent = c
        break

    # If patient confirms the transfer, record active patient consent automatically
    if not active_consent and user.role == UserRole.PATIENT:
        consent_id = f"CNS-{uuid.uuid4().hex[:8].upper()}"
        active_consent = Consent(
            id=consent_id,
            patient_id=transfer.patient_id,
            org_id=transfer.from_hospital_id,
            granted_to_hospital_id=transfer.to_hospital_id,
            purpose=transfer.reason or "Continuity of fertility care",
            scope="ALL_RECORDS",
            consent_type="external_transfer",
            status="ACTIVE",
            granted_at=now,
            granted_by=user.username or "Patient",
            recorded_on_behalf=False,
            created_at=now,
        )
        db.add(active_consent)
        db.commit()

    if not active_consent:
        db.commit()
        raise AppException(
            status_code=409,
            code="CONSENT_REQUIRED",
            message=f"Active patient consent for receiving hospital '{transfer.to_hospital_id}' is required before accepting a transfer.",
        )

    # 1. Sending hospital access becomes READ_ONLY (ACTIVE)
    from_pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == transfer.patient_id,
            PatientHospitalAccess.hospital_id == transfer.from_hospital_id,
        )
    )
    if from_pha:
        from_pha.access_level = HospitalAccessLevel.READ_ONLY
        from_pha.status = HospitalAccessStatus.ACTIVE
        db.add(from_pha)
    else:
        from_pha = PatientHospitalAccess(
            id=f"PHA-{uuid.uuid4().hex[:8].upper()}",
            patient_id=transfer.patient_id,
            hospital_id=transfer.from_hospital_id,
            access_level=HospitalAccessLevel.READ_ONLY,
            status=HospitalAccessStatus.ACTIVE,
            since=now,
        )
        db.add(from_pha)

    # 2. Receiving hospital access becomes READ_WRITE (ACTIVE)
    to_pha = db.scalar(
        select(PatientHospitalAccess).where(
            PatientHospitalAccess.patient_id == transfer.patient_id,
            PatientHospitalAccess.hospital_id == transfer.to_hospital_id,
        )
    )
    if to_pha:
        to_pha.access_level = HospitalAccessLevel.READ_WRITE
        to_pha.status = HospitalAccessStatus.ACTIVE
        to_pha.source_transfer_id = transfer.id
        to_pha.since = now
        db.add(to_pha)
    else:
        to_pha = PatientHospitalAccess(
            id=f"PHA-{uuid.uuid4().hex[:8].upper()}",
            patient_id=transfer.patient_id,
            hospital_id=transfer.to_hospital_id,
            access_level=HospitalAccessLevel.READ_WRITE,
            status=HospitalAccessStatus.ACTIVE,
            source_transfer_id=transfer.id,
            since=now,
        )
        db.add(to_pha)

    # 2.5 Auto-assign receiving hospital doctors so they can examine the transferred patient immediately
    receiving_docs = db.scalars(
        select(User).where(
            User.role == UserRole.DOCTOR,
            or_(
                User.hospital_id == transfer.to_hospital_id,
                User.org_id == transfer.to_hospital_id,
            ),
        )
    ).all()
    for doc in receiving_docs:
        existing_dp = db.scalar(
            select(DoctorPatient).where(
                DoctorPatient.doctor_id == doc.id,
                DoctorPatient.patient_id == transfer.patient_id,
            )
        )
        if not existing_dp:
            db.add(DoctorPatient(
                doctor_id=doc.id,
                patient_id=transfer.patient_id,
            ))

    # 3. Mark transfer status COMPLETED
    transfer.status = TransferRequestStatus.COMPLETED
    transfer.decided_by = user.id
    transfer.decided_at = now
    transfer.consent_id = active_consent.id
    db.add(transfer)

    # 4. Invalidate patient summaries (marked stale)
    summaries = db.scalars(
        select(Summary).where(Summary.patient_id == transfer.patient_id)
    ).all()
    for s in summaries:
        if isinstance(s.content_json, dict):
            c_dict = dict(s.content_json)
            c_dict["is_stale"] = True
            s.content_json = c_dict
        db.add(s)

    # 5. Audit log
    record_audit(
        db,
        user_id=user.id,
        action="ACCEPT_TRANSFER",
        patient_id=transfer.patient_id,
        org_id=transfer.to_hospital_id,
    )

    db.commit()
    db.refresh(transfer)
    return transfer


def reject_transfer_request(
    db: Session,
    user: User,
    transfer_id: str,
    reason: Optional[str] = None,
) -> TransferRequest:
    """Receiving hospital admin rejects the transfer request. Idempotent."""
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Transfer request '{transfer_id}' not found",
        )

    if transfer.status == TransferRequestStatus.REJECTED:
        return transfer

    if transfer.status == TransferRequestStatus.COMPLETED:
        raise AppException(
            status_code=400,
            code="INVALID_STATE",
            message="Completed transfers cannot be rejected.",
        )

    if user.role == UserRole.PATIENT:
        if user.patient_id != transfer.patient_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Patients can only revoke transfers for their own medical records ({user.patient_id}).",
            )
    elif user.role not in (UserRole.ADMIN, UserRole.OVA_ADMIN):
        user_hosp = user.hospital_id or user.org_id
        if user_hosp != transfer.to_hospital_id and user_hosp != transfer.from_hospital_id:
            raise AppException(
                status_code=403,
                code="FORBIDDEN",
                message=f"Unauthorized to reject this transfer request.",
            )

    transfer.status = TransferRequestStatus.REJECTED
    transfer.decided_by = user.id
    transfer.decided_at = datetime.now(timezone.utc)
    if reason:
        transfer.reason = reason
    db.add(transfer)

    record_audit(
        db,
        user_id=user.id,
        action="REJECT_TRANSFER",
        patient_id=transfer.patient_id,
        org_id=transfer.to_hospital_id,
    )
    db.commit()
    db.refresh(transfer)
    return transfer


def cancel_transfer_request(
    db: Session,
    user: User,
    transfer_id: str,
) -> TransferRequest:
    """Cancels a pending transfer request (by patient or sending hospital). Idempotent."""
    transfer = db.get(TransferRequest, transfer_id)
    if not transfer:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Transfer request '{transfer_id}' not found",
        )

    if transfer.status == TransferRequestStatus.CANCELLED:
        return transfer

    if transfer.status != TransferRequestStatus.REQUESTED:
        raise AppException(
            status_code=400,
            code="INVALID_STATE",
            message=f"Transfer with status {transfer.status.value} cannot be cancelled.",
        )

    user_hosp = user.hospital_id or user.org_id
    if user.role == UserRole.PATIENT and user.patient_id != transfer.patient_id:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Patients can only cancel their own transfer requests.",
        )
    if user.role in (UserRole.HOSPITAL_ADMIN, UserRole.STAFF) and user_hosp != transfer.from_hospital_id:
        raise AppException(
            status_code=403,
            code="FORBIDDEN",
            message="Only sending hospital administrators can cancel this request.",
        )

    transfer.status = TransferRequestStatus.CANCELLED
    db.add(transfer)

    record_audit(
        db,
        user_id=user.id,
        action="CANCEL_TRANSFER",
        patient_id=transfer.patient_id,
        org_id=transfer.from_hospital_id,
    )
    db.commit()
    db.refresh(transfer)
    return transfer
