from app.schemas.base import BaseReadSchema


class OrganizationRead(BaseReadSchema):
    id: str
    name: str
    type: str = "hospital"
