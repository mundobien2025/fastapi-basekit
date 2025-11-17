"""Schemas para usuarios con agregaciones."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserWithStatsSchema(BaseModel):
    """Schema de usuario con estadísticas agregadas."""

    id: int
    name: str
    email: EmailStr
    created_at: datetime
    referidos_count: int
    total_orders: Optional[int] = None
    total_spent: Optional[int] = None  # En centavos

    class Config:
        from_attributes = True


class UserSchema(BaseModel):
    """Schema básico de usuario."""

    id: int
    name: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreateSchema(BaseModel):
    """Schema para crear usuario."""

    name: str
    email: EmailStr

