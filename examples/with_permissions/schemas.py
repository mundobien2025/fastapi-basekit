"""Schemas para usuarios con permisos."""

from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserSchema(BaseModel):
    """Schema de usuario."""

    id: int
    name: str
    email: EmailStr
    is_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreateSchema(BaseModel):
    """Schema para crear usuario."""

    name: str
    email: EmailStr
    is_admin: bool = False

