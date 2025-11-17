# app/schemas/base_response.py

from datetime import datetime
from typing import Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict

try:  # pragma: no cover - dependencia opcional
    from beanie import PydanticObjectId  # type: ignore
except ImportError:  # pragma: no cover
    PydanticObjectId = str  # type: ignore[assignment, misc]

# Define un tipo genérico
T = TypeVar("T")

BaseSchemaId = Union[str, "PydanticObjectId"]  # type: ignore[name-defined]


class BaseSchema(BaseModel):
    id: BaseSchemaId
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
