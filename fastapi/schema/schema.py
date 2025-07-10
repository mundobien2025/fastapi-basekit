# app/schemas/base_response.py

from datetime import datetime
from typing import Optional, TypeVar
from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict

# Define un tipo genérico
T = TypeVar("T")


class BaseSchema(BaseModel):
    id: PydanticObjectId
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
