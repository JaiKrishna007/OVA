from datetime import date
from typing import TYPE_CHECKING, Optional, Any
from sqlalchemy import (
    String,
    Date,
    Integer,
    Float,
    Text,
    JSON,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.mixins import ClinicalTableMixin
from app.models.enums import (
    TreatmentEventKind,
    InvestigationCategory,
    InvestigationStatus,
    EmbryoFate,
    TransferKind,
    PregnancyResult,
    FollowupStatus,
)

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.cycle import Cycle


class TreatmentEvent(Base, ClinicalTableMixin):
    __tablename__ = "treatment_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    kind: Mapped[TreatmentEventKind] = mapped_column(
        SAEnum(TreatmentEventKind, native_enum=False),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="treatment_events",
    )


class Investigation(Base, ClinicalTableMixin):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
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
    category: Mapped[InvestigationCategory] = mapped_column(
        SAEnum(InvestigationCategory, native_enum=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ref_range: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[InvestigationStatus] = mapped_column(
        SAEnum(InvestigationStatus, native_enum=False),
        nullable=False,
    )
    ordered_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="investigations",
    )
    cycle: Mapped[Optional["Cycle"]] = relationship(
        "Cycle",
        back_populates="investigations",
    )


class Medication(Base, ClinicalTableMixin):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    dose: Mapped[str] = mapped_column(String, nullable=False)
    route: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="medications",
    )


class StimulationDay(Base, ClinicalTableMixin):
    __tablename__ = "stimulation_days"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    day_no: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    follicles: Mapped[Any] = mapped_column(JSON, nullable=False)
    e2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p4: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    endometrium_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="stimulation_days",
    )


class OocyteRetrieval(Base, ClinicalTableMixin):
    __tablename__ = "oocyte_retrievals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    oocytes_retrieved: Mapped[int] = mapped_column(Integer, nullable=False)
    mii: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gv: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="oocyte_retrievals",
    )


class Embryo(Base, ClinicalTableMixin):
    __tablename__ = "embryos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    embryo_label: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pgt_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fate: Mapped[EmbryoFate] = mapped_column(
        SAEnum(EmbryoFate, native_enum=False),
        nullable=False,
    )
    storage_location: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="embryos",
    )


class Transfer(Base, ClinicalTableMixin):
    __tablename__ = "transfers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[TransferKind] = mapped_column(
        SAEnum(TransferKind, native_enum=False),
        nullable=False,
    )
    embryo_ids: Mapped[Any] = mapped_column(JSON, nullable=False)
    endometrium_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="transfers",
    )


class PregnancyOutcome(Base, ClinicalTableMixin):
    __tablename__ = "pregnancy_outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    beta_hcg_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    beta_hcg_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    result: Mapped[PregnancyResult] = mapped_column(
        SAEnum(PregnancyResult, native_enum=False),
        nullable=False,
    )
    gestation_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="pregnancy_outcomes",
    )


class AdverseEvent(Base, ClinicalTableMixin):
    __tablename__ = "adverse_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cycle_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cycles.id"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    management_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    cycle: Mapped["Cycle"] = relationship(
        "Cycle",
        back_populates="adverse_events",
    )


class DoctorNote(Base, ClinicalTableMixin):
    __tablename__ = "doctor_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
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
    date: Mapped[date] = mapped_column(Date, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="doctor_notes",
    )
    cycle: Mapped[Optional["Cycle"]] = relationship(
        "Cycle",
        back_populates="doctor_notes",
    )


class Followup(Base, ClinicalTableMixin):
    __tablename__ = "followups"

    id: Mapped[str] = mapped_column(String, primary_key=True)
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
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[FollowupStatus] = mapped_column(
        SAEnum(FollowupStatus, native_enum=False),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="followups",
    )
    cycle: Mapped[Optional["Cycle"]] = relationship(
        "Cycle",
        back_populates="followups",
    )
