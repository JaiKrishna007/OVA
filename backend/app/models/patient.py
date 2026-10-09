from datetime import date
from typing import TYPE_CHECKING, List, Optional, Any
from sqlalchemy import String, Date, Float, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.cycle import Cycle
    from app.models.clinical import Investigation, DoctorNote, Followup
    from app.models.source_record import SourceRecord
    from app.models.summary import Summary


class DoctorPatient(Base):
    __tablename__ = "doctor_patients"

    doctor_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id"),
        primary_key=True,
    )
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        primary_key=True,
        index=True,
    )

    doctor: Mapped["User"] = relationship(
        "User",
        back_populates="doctor_patients",
    )
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="doctor_patients",
    )


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    dob: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String, nullable=False)
    org_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    diagnosis: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    partner_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blood_group: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bmi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="patients",
    )
    doctor_patients: Mapped[List["DoctorPatient"]] = relationship(
        "DoctorPatient",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    cycles: Mapped[List["Cycle"]] = relationship(
        "Cycle",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    doctor_notes: Mapped[List["DoctorNote"]] = relationship(
        "DoctorNote",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    followups: Mapped[List["Followup"]] = relationship(
        "Followup",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    source_records: Mapped[List["SourceRecord"]] = relationship(
        "SourceRecord",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[List["Summary"]] = relationship(
        "Summary",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
