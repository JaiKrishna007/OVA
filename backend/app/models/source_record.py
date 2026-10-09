from datetime import date
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Date, Text, Integer, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import TrustStatus, SourceProcessingStatus

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.cycle import Cycle
    from app.models.user import User


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    cycle_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("cycles.id", use_alter=True),
        index=True,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    origin_org: Mapped[str] = mapped_column(String, nullable=False)
    trust_status: Mapped[TrustStatus] = mapped_column(
        SAEnum(TrustStatus, native_enum=False),
        nullable=False,
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    uploaded_by: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        default=None,
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        default="text/plain",
    )
    file_path: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        default=None,
    )
    processing_status: Mapped[SourceProcessingStatus] = mapped_column(
        SAEnum(SourceProcessingStatus, native_enum=False),
        nullable=False,
        default=SourceProcessingStatus.VALIDATED,
        index=True,
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        default=None,
    )

    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by],
    )

    __table_args__ = (
        UniqueConstraint("id", "version", name="uq_source_records_id_version"),
    )

    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="source_records",
    )
    cycle: Mapped[Optional["Cycle"]] = relationship(
        "Cycle",
        foreign_keys=[cycle_id],
    )
