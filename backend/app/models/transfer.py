from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import String, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Consent(Base):
    """Tracks patient consent to import external records from other clinics."""
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    org_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    granted_to_hospital_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        nullable=True,
        default=None,
        index=True,
    )
    purpose: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="Continuity of fertility care")
    scope: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="ALL_RECORDS")
    consent_type: Mapped[str] = mapped_column(String, nullable=False, default="external_transfer")
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")  # ACTIVE, REVOKED, EXPIRED
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    granted_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # patient, legal_guardian
    recorded_on_behalf: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", foreign_keys=[patient_id])
    granted_to_hospital = relationship("Organization", foreign_keys=[granted_to_hospital_id])


class IdentityLink(Base):
    """Tracks verified cross-clinic identity matches between external records and internal patient IDs."""
    __tablename__ = "identity_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    internal_patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    external_patient_id: Mapped[str] = mapped_column(String, nullable=False)
    external_org_name: Mapped[str] = mapped_column(String, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    match_criteria_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending, confirmed, rejected
    confirmed_by: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", foreign_keys=[internal_patient_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])


class ImportBatch(Base):
    """Quarantine store for imported external clinic batches awaiting validation, consent, and staff review."""
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    uploaded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    origin_org: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="quarantined")  # quarantined, confirmed, rejected
    raw_payload_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    validation_report_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    identity_match_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    cycle_suggestions_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    target_patient_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("patients.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    uploader = relationship("User", foreign_keys=[uploaded_by])
    target_patient = relationship("Patient", foreign_keys=[target_patient_id])
