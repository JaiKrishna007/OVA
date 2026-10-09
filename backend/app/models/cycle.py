from datetime import date
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Date, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import CycleType, TrustStatus

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.organization import Organization
    from app.models.source_record import SourceRecord
    from app.models.clinical import (
        TreatmentEvent,
        Investigation,
        Medication,
        StimulationDay,
        OocyteRetrieval,
        Embryo,
        Transfer,
        PregnancyOutcome,
        AdverseEvent,
        DoctorNote,
        Followup,
    )


class Cycle(Base):
    __tablename__ = "cycles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[CycleType] = mapped_column(
        SAEnum(CycleType, native_enum=False),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    origin_org: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    external_cycle_no: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Optional clinical provenance fields
    source_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("source_records.id"),
        index=True,
        nullable=True,
    )
    org_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        nullable=True,
    )
    trust_status: Mapped[Optional[TrustStatus]] = mapped_column(
        SAEnum(TrustStatus, native_enum=False),
        nullable=True,
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="cycles",
    )
    source_record: Mapped[Optional["SourceRecord"]] = relationship(
        "SourceRecord",
        foreign_keys=[source_id],
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        foreign_keys=[org_id],
    )

    treatment_events: Mapped[List["TreatmentEvent"]] = relationship(
        "TreatmentEvent",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    medications: Mapped[List["Medication"]] = relationship(
        "Medication",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    stimulation_days: Mapped[List["StimulationDay"]] = relationship(
        "StimulationDay",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    oocyte_retrievals: Mapped[List["OocyteRetrieval"]] = relationship(
        "OocyteRetrieval",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    embryos: Mapped[List["Embryo"]] = relationship(
        "Embryo",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    transfers: Mapped[List["Transfer"]] = relationship(
        "Transfer",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    pregnancy_outcomes: Mapped[List["PregnancyOutcome"]] = relationship(
        "PregnancyOutcome",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    adverse_events: Mapped[List["AdverseEvent"]] = relationship(
        "AdverseEvent",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    doctor_notes: Mapped[List["DoctorNote"]] = relationship(
        "DoctorNote",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
    followups: Mapped[List["Followup"]] = relationship(
        "Followup",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )
