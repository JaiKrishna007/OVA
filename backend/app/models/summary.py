from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Any
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_version: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    content_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    validator_report_json: Mapped[Any] = mapped_column(JSON, nullable=False)

    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="summaries",
    )
    feedbacks: Mapped[List["SummaryFeedback"]] = relationship(
        "SummaryFeedback",
        back_populates="summary",
        cascade="all, delete-orphan",
    )


class SummaryFeedback(Base):
    __tablename__ = "summary_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    summary_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("summaries.id"),
        index=True,
        nullable=False,
    )
    statement_ref: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=False,
    )
    at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    summary: Mapped["Summary"] = relationship(
        "Summary",
        back_populates="feedbacks",
    )
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
