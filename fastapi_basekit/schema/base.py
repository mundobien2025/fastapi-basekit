# app/schemas/base_response.py

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

# Define un tipo genérico
T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    message: str = "Operación exitosa"
    status: str = "success"

    model_config = ConfigDict(from_attributes=True)


class BasePaginationResponse(BaseModel, Generic[T]):
    data: List[T]
    message: str = "Operación exitosa"
    status: str = "success"
    pagination: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)
