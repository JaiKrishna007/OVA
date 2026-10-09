from pydantic import BaseModel, ConfigDict


class BaseReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
