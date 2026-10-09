from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    metrics_json: Mapped[Any] = mapped_column(JSON, nullable=False)
