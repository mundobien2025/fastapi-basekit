"""SQLModel model fixture for tests."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users_sqlmodel"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=100, unique=True, index=True)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    deleted_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
