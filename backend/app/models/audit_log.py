from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
        default="",
    )
    hospital_id: Mapped[str] = mapped_column(
        String,
        index=True,
        nullable=False,
        default="",
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    patient_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=True,
    )
    event_type: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        default=None,
    )
    details: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    outcome: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        default="success",
    )
    at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    patient: Mapped[Optional["Patient"]] = relationship(
        "Patient",
        foreign_keys=[patient_id],
    )
