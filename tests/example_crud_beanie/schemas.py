"""Schemas Pydantic para validación de datos Beanie."""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBeanieSchema(BaseModel):
    """Schema de respuesta de usuario para Beanie."""

    id: str
    name: str
    email: EmailStr
    age: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserBeanieCreateSchema(BaseModel):
    """Schema para crear usuario en MongoDB."""

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: Optional[int] = Field(None, ge=0, le=150)
    is_active: bool = True


class UserBeanieUpdateSchema(BaseModel):
    """Schema para actualizar usuario en MongoDB."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    is_active: Optional[bool] = None
