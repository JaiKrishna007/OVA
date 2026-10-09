from typing import Optional
from app.models.enums import UserRole
from app.schemas.base import BaseReadSchema


class UserRead(BaseReadSchema):
    id: str
    username: str
    role: UserRole
    org_id: str
    hospital_id: Optional[str] = None
    patient_id: Optional[str] = None
    password_hash: Optional[str] = None
