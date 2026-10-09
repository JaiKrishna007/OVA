from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.patient import DoctorPatient, Patient


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False),
        nullable=False,
    )
    org_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        nullable=False,
    )
    hospital_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("organizations.id"),
        nullable=True,
        default=None,
        index=True,
    )
    patient_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("patients.id"),
        nullable=True,
        default=None,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[org_id],
        back_populates="users",
    )
    hospital: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        foreign_keys=[hospital_id],
    )
    patient: Mapped[Optional["Patient"]] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
    doctor_patients: Mapped[List["DoctorPatient"]] = relationship(
        "DoctorPatient",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
