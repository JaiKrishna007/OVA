"""
Centralized AuditService — single entry point for all audit log writes.

Event type constants enforce a closed vocabulary; callers import from here.
Rules (append-only, never secrets):
  - Never store full clinical text in `details`.
  - Never store passwords, tokens, or PII beyond what is needed for forensic tracing.
  - Every write is committed immediately (no deferred/bulk writes) so a crash cannot
    silently drop audit entries.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

# ---------------------------------------------------------------------------
# Typed event-type constants — import and use these everywhere.
# ---------------------------------------------------------------------------

class AuditEvent:
    # Authentication
    LOGIN              = "LOGIN"
    LOGOUT             = "LOGOUT"
    ACCESS_DENIED      = "ACCESS_DENIED"

    # Patient
    PATIENT_VIEWED     = "PATIENT_VIEWED"

    # Records
    RECORD_VIEWED      = "RECORD_VIEWED"
    RECORD_UPLOADED    = "RECORD_UPLOADED"

    # Extraction
    EXTRACTION_RUN     = "EXTRACTION_RUN"

    # Claims
    CLAIM_VERIFIED     = "CLAIM_VERIFIED"   # programmatic validator accepted
    CLAIM_ACCEPTED     = "CLAIM_ACCEPTED"   # clinician manually accepted
    CLAIM_REJECTED     = "CLAIM_REJECTED"   # clinician manually rejected

    # Conflicts
    CONFLICT_DETECTED      = "CONFLICT_DETECTED"
    CONFLICT_ACKNOWLEDGED  = "CONFLICT_ACKNOWLEDGED"

    # Gaps
    GAP_DETECTED       = "GAP_DETECTED"

    # Summaries
    SUMMARY_GENERATED  = "SUMMARY_GENERATED"

    # Ask-the-chart
    ASK_ALLOWED        = "ASK_ALLOWED"
    S1_BLOCK           = "S1_BLOCK"

    # Consents
    CONSENT_GRANTED    = "CONSENT_GRANTED"
    CONSENT_REVOKED    = "CONSENT_REVOKED"

    # Transfers
    TRANSFER_REQUESTED = "TRANSFER_REQUESTED"
    TRANSFER_ACCEPTED  = "TRANSFER_ACCEPTED"
    TRANSFER_REJECTED  = "TRANSFER_REJECTED"
    TRANSFER_CANCELLED = "TRANSFER_CANCELLED"


class AuditOutcome:
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    DENIED  = "denied"


class AuditService:
    """
    Thin service wrapping the audit_log table.

    Usage (in a router / service that already holds a db session)::

        from app.services.audit_service import AuditService, AuditEvent
        AuditService.log(
            db=db,
            user=current_user,
            event_type=AuditEvent.PATIENT_VIEWED,
            patient_id=patient_id,
            details={"source": "GET /patients/{id}"},
        )
    """

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    @staticmethod
    def log(
        db: Session,
        *,
        user_id: str,
        role: str,
        org_id: str,
        hospital_id: Optional[str] = None,
        event_type: str,
        patient_id: Optional[str] = None,
        record_id: Optional[str] = None,
        claim_id: Optional[str] = None,
        outcome: str = AuditOutcome.SUCCESS,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Write a single audit log row and commit immediately.

        Parameters
        ----------
        db          : Active SQLAlchemy session.
        user_id     : Authenticated user's database ID.
        role        : User's role at the time of the event.
        org_id      : User's home organisation (tenant isolation).
        hospital_id : User's hospital (may differ from org_id for cross-hospital
                      delegations).  Falls back to org_id if omitted.
        event_type  : One of the AuditEvent constants.
        patient_id  : Patient this event relates to (None for system events).
        record_id   : Source record this event relates to.
        claim_id    : Clinical claim this event relates to.
        outcome     : AuditOutcome constant.  Defaults to "success".
        details     : Optional dict with non-sensitive metadata.  Never store
                      full clinical text, passwords, tokens, or raw file content.
        """
        # Safety guard: prevent accidental secret storage
        if details:
            details = AuditService._sanitize_details(details)

        eff_hospital = hospital_id or org_id
        eff_org      = org_id or hospital_id or "ORG-DEFAULT"

        safe_details: Dict[str, Any] = {}
        if details:
            safe_details.update(details)
        if record_id:
            safe_details["record_id"] = record_id
        if claim_id:
            safe_details["claim_id"] = claim_id
        if role:
            safe_details["role"] = role

        legacy_action_map = {
            AuditEvent.PATIENT_VIEWED: "patient_view",
            AuditEvent.CLAIM_ACCEPTED: "claim_accept",
            AuditEvent.CLAIM_REJECTED: "claim_reject",
            AuditEvent.RECORD_UPLOADED: "record_upload",
            AuditEvent.RECORD_VIEWED: "record_view",
            AuditEvent.LOGIN: "login",
            AuditEvent.LOGOUT: "logout",
            AuditEvent.SUMMARY_GENERATED: "summary_generate",
        }
        action_val = (details.get("action") if details and "action" in details else None) or legacy_action_map.get(event_type, event_type)

        log_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        entry = AuditLog(
            id=log_id,
            org_id=eff_org,
            hospital_id=eff_hospital,
            user_id=user_id,
            action=action_val,
            patient_id=patient_id,
            event_type=event_type,
            details=safe_details or None,
            outcome=outcome,
            at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def log_from_user(
        db: Session,
        user: Any,
        event_type: str,
        patient_id: Optional[str] = None,
        record_id: Optional[str] = None,
        claim_id: Optional[str] = None,
        outcome: str = AuditOutcome.SUCCESS,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Convenience wrapper that extracts user fields automatically.
        Accepts any object with .id, .role, .org_id, and optionally .hospital_id.
        """
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        return AuditService.log(
            db=db,
            user_id=user.id,
            role=role_val,
            org_id=user.org_id,
            hospital_id=getattr(user, "hospital_id", None),
            event_type=event_type,
            patient_id=patient_id,
            record_id=record_id,
            claim_id=claim_id,
            outcome=outcome,
            details=details,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _REDACTED_KEYS = frozenset({
        "password", "token", "secret", "key", "hash",
        "content_text", "raw_text", "full_text",
    })

    @staticmethod
    def _sanitize_details(d: Dict[str, Any]) -> Dict[str, Any]:
        """Strip any keys that look like secrets or full clinical text."""
        return {
            k: "[REDACTED]" if k.lower() in AuditService._REDACTED_KEYS else v
            for k, v in d.items()
            if v is not None
        }
