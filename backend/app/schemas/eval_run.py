from datetime import datetime
from typing import Any
from app.schemas.base import BaseReadSchema


class EvalRunRead(BaseReadSchema):
    id: str
    run_at: datetime
    provider: str
    metrics_json: Any
