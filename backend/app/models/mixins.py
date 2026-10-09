from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr
from app.models.enums import TrustStatus

if TYPE_CHECKING:
    from app.models.source_record import SourceRecord
    from app.models.organization import Organization


class ClinicalTableMixin:
    """Mixin providing mandatory clinical provenance fields."""

    @declared_attr
    def source_id(cls) -> Mapped[str]:
        return mapped_column(
            String,
            ForeignKey("source_records.id"),
            index=True,
            nullable=False,
        )

    @declared_attr
    def org_id(cls) -> Mapped[str]:
        """
        Hospital scoping: org_id on clinical rows is the hospital that created it (origin),
        which does not change on transfer.
        """
        return mapped_column(
            String,
            ForeignKey("organizations.id"),
            nullable=False,
        )

    @declared_attr
    def origin_org(cls) -> Mapped[str]:
        return mapped_column(String, nullable=False)

    @declared_attr
    def trust_status(cls) -> Mapped[TrustStatus]:
        return mapped_column(
            SAEnum(TrustStatus, native_enum=False),
            nullable=False,
        )

    @declared_attr
    def source_record(cls) -> Mapped["SourceRecord"]:
        return relationship(
            "SourceRecord",
            foreign_keys=[cls.source_id],
        )

    @declared_attr
    def organization(cls) -> Mapped["Organization"]:
        return relationship(
            "Organization",
            foreign_keys=[cls.org_id],
        )
