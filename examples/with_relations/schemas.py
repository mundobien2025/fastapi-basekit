"""Schemas para usuarios con relaciones."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr


class RoleSchema(BaseModel):
    """Schema de rol."""

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserSchema(BaseModel):
    """Schema de usuario con rol."""

    id: int
    name: str
    email: EmailStr
    role_id: Optional[int] = None
    created_at: datetime
    role: Optional[RoleSchema] = None
    roles: List[RoleSchema] = []

    class Config:
        from_attributes = True


class UserCreateSchema(BaseModel):
    """Schema para crear usuario."""

    name: str
    email: EmailStr
    role_id: Optional[int] = None

