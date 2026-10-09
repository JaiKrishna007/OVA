from typing import TYPE_CHECKING, List
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False, default="hospital")

    users: Mapped[List["User"]] = relationship(
        "User",
        primaryjoin="Organization.id == User.org_id",
        foreign_keys="[User.org_id]",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    patients: Mapped[List["Patient"]] = relationship(
        "Patient",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
