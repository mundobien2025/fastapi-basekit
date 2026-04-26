"""Base Pydantic schema with ORM serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%S")},
    )
