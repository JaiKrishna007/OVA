"""
OVA v2 Provenance, Claims Ledger, Conflicts, Documentation Gaps, and Cross-Hospital Access Models.
Explicit hospital scoping: org_id / hospital_id on clinical claims is the originating hospital, immutable on transfer.
"""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional, Any, List
from sqlalchemy import (
    String,
    Date,
    Float,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import (
    ClaimValidationStatus,
    ExtractionMethod,
    ConflictStatus,
    GapStatus,
    TransferRequestStatus,
    HospitalAccessLevel,
    HospitalAccessStatus,
)

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.cycle import Cycle
    from app.models.organization import Organization
    from app.models.source_record import SourceRecord
    from app.models.user import User
    from app.models.transfer import Consent


class ClinicalClaim(Base):
    """
    Persistent ledger of all validated and raw candidate clinical claims extracted from sources or backfilled from seed.
    Hospital scoping: hospital_id is the hospital that created/originated the claim; immutable on transfer.
    """
    __tablename__ = "clinical_claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # CLM-####
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    hospital_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        index=True,
        nullable=False,
    )
    source_record_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("source_records.id"),
        index=True,
        nullable=False,
    )
    cycle_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=True,
    )
    cycle_assignment: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        default="ASSIGNED",
    )
    field: Mapped[str] = mapped_column(String, index=True, nullable=False)
    value_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value_num: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    span_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    span_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        SAEnum(ExtractionMethod, native_enum=False),
        nullable=False,
        default=ExtractionMethod.SEED,
    )
    validation_status: Mapped[ClaimValidationStatus] = mapped_column(
        SAEnum(ClaimValidationStatus, native_enum=False),
        nullable=False,
        default=ClaimValidationStatus.VERIFIED,
        index=True,
    )
    validation_checks: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    reason_codes: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    uploaded_by: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    materialized_table: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    materialized_row_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_clinical_claims_patient_field_status", "patient_id", "field", "validation_status"),
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
    hospital: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[hospital_id],
    )
    source_record: Mapped["SourceRecord"] = relationship(
        "SourceRecord",
        foreign_keys=[source_record_id],
    )
    cycle: Mapped[Optional["Cycle"]] = relationship(
        "Cycle",
        foreign_keys=[cycle_id],
    )
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by],
    )


class ConflictRecord(Base):
    """
    Persistent conflict ledger between discordant clinical claims.
    Conflicting values from different sources or hospitals are preserved side-by-side.
    """
    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # CONF-####
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    field: Mapped[str] = mapped_column(String, index=True, nullable=False)
    claim_ids: Mapped[Any] = mapped_column(JSON, nullable=False)
    claim_a_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("clinical_claims.id"),
        nullable=True,
    )
    claim_b_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("clinical_claims.id"),
        nullable=True,
    )
    hospital_a: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hospital_b: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_a: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_b: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_a: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_b: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value_a: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value_b: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_text: Mapped[str] = mapped_column(
        String,
        default="Conflicting documented values. Clinician review required.",
        nullable=False,
    )
    status: Mapped[ConflictStatus] = mapped_column(
        SAEnum(ConflictStatus, native_enum=False),
        nullable=False,
        default=ConflictStatus.OPEN,
        index=True,
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
    acknowledged_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[acknowledged_by],
    )
    claim_a: Mapped[Optional["ClinicalClaim"]] = relationship(
        "ClinicalClaim",
        foreign_keys=[claim_a_id],
    )
    claim_b: Mapped[Optional["ClinicalClaim"]] = relationship(
        "ClinicalClaim",
        foreign_keys=[claim_b_id],
    )


class DocumentationGap(Base):
    """
    Persistent clinical documentation gap alerts when mandatory protocol records are missing.
    """
    __tablename__ = "documentation_gaps"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # GAP-####
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    cycle_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=True,
    )
    rule_id: Mapped[str] = mapped_column(String, nullable=False)
    trigger_claim_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("clinical_claims.id"),
        nullable=True,
    )
    expected_item: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[GapStatus] = mapped_column(
        SAEnum(GapStatus, native_enum=False),
        nullable=False,
        default=GapStatus.OPEN,
        index=True,
    )
    resolving_claim_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("clinical_claims.id"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
    cycle: Mapped[Optional["Cycle"]] = relationship(
        "Cycle",
        foreign_keys=[cycle_id],
    )
    trigger_claim: Mapped[Optional["ClinicalClaim"]] = relationship(
        "ClinicalClaim",
        foreign_keys=[trigger_claim_id],
    )
    resolving_claim: Mapped[Optional["ClinicalClaim"]] = relationship(
        "ClinicalClaim",
        foreign_keys=[resolving_claim_id],
    )
    acknowledged_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[acknowledged_by],
    )


class TransferRequest(Base):
    """
    Cross-hospital record transfer request workflow between sending and receiving clinics.
    """
    __tablename__ = "transfer_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # TRF-####
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    from_hospital_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        index=True,
        nullable=False,
    )
    to_hospital_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        index=True,
        nullable=False,
    )
    requested_by: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=False,
    )
    status: Mapped[TransferRequestStatus] = mapped_column(
        SAEnum(TransferRequestStatus, native_enum=False),
        nullable=False,
        default=TransferRequestStatus.REQUESTED,
        index=True,
    )
    consent_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("consents.id"),
        nullable=True,
    )
    decided_by: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
    from_hospital: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[from_hospital_id],
    )
    to_hospital: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[to_hospital_id],
    )
    requester: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_by],
    )
    decider: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[decided_by],
    )
    consent: Mapped[Optional["Consent"]] = relationship(
        "Consent",
        foreign_keys=[consent_id],
    )


class PatientHospitalAccess(Base):
    """
    Active or revoked delegation grants for hospital access to patient charts.
    """
    __tablename__ = "patient_hospital_access"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # PHA-####
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    hospital_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        index=True,
        nullable=False,
    )
    access_level: Mapped[HospitalAccessLevel] = mapped_column(
        SAEnum(HospitalAccessLevel, native_enum=False),
        nullable=False,
        default=HospitalAccessLevel.READ_ONLY,
    )
    status: Mapped[HospitalAccessStatus] = mapped_column(
        SAEnum(HospitalAccessStatus, native_enum=False),
        nullable=False,
        default=HospitalAccessStatus.ACTIVE,
        index=True,
    )
    source_transfer_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("transfer_requests.id"),
        nullable=True,
    )
    since: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_patient_hospital_access_patient_hospital", "patient_id", "hospital_id"),
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
    hospital: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[hospital_id],
    )
    source_transfer: Mapped[Optional["TransferRequest"]] = relationship(
        "TransferRequest",
        foreign_keys=[source_transfer_id],
    )
