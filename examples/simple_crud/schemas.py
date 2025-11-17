"""Schemas Pydantic para usuarios."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserSchema(BaseModel):
    """Schema para representar un usuario."""

    id: int
    name: str
    email: EmailStr
    age: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreateSchema(BaseModel):
    """Schema para crear un usuario."""

    name: str = Field(..., min_length=1, max_length=100, description="Nombre del usuario")
    email: EmailStr = Field(..., description="Email único del usuario")
    age: Optional[int] = Field(None, ge=0, le=150, description="Edad del usuario")
    is_active: bool = Field(True, description="Si el usuario está activo")


class UserUpdateSchema(BaseModel):
    """Schema para actualizar un usuario."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    is_active: Optional[bool] = None

