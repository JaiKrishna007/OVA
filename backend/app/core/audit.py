import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    user_id: str,
    action: str,
    patient_id: Optional[str] = None,
    org_id: Optional[str] = None,
    hospital_id: Optional[str] = None,
    event_type: Optional[str] = None,
    details: Optional[Any] = None,
    outcome: Optional[str] = "success",
) -> AuditLog:
    """Writes an audit log entry to audit_log table and flushes/commits."""
    from app.models.user import User
    from app.models.patient import Patient

    if not org_id and not hospital_id:
        user = db.get(User, user_id)
        if user and user.org_id:
            org_id = user.org_id
        elif patient_id:
            pat = db.get(Patient, patient_id)
            if pat and pat.org_id:
                org_id = pat.org_id
        if not org_id:
            org_id = "ORG-DEFAULT"

    eff_org = org_id or hospital_id or "ORG-DEFAULT"
    eff_hospital = hospital_id or org_id or "ORG-DEFAULT"

    log_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
    entry = AuditLog(
        id=log_id,
        org_id=eff_org,
        hospital_id=eff_hospital,
        user_id=user_id,
        action=action,
        patient_id=patient_id,
        event_type=event_type,
        details=details,
        outcome=outcome,
        at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
