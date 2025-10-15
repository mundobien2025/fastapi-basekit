"""Modelos Beanie (MongoDB) para pruebas."""

from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field


class UserDocument(Document):
    """Modelo de usuario para MongoDB con Beanie."""

    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None

    class Settings:
        name = "users"  # Collection name
        indexes = [
            "email",  # Index on email
        ]

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "is_active": True,
            }
        }

    def __repr__(self):
        return f"<UserDocument(id={self.id}, name='{self.name}', email='{self.email}')>"
