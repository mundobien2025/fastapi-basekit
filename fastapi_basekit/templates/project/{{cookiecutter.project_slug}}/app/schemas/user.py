"""User schemas."""

{% if cookiecutter.orm == "sqlalchemy" -%}
import uuid
{%- endif %}
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRoleEnum
from app.schemas.base import BaseSchema


class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=200)
    role: UserRoleEnum = UserRoleEnum.user
    model_config = ConfigDict(extra="ignore")


class UserUpdateSchema(BaseModel):
    full_name: Optional[str] = Field(None, max_length=200)
    role: Optional[UserRoleEnum] = None
    is_active: Optional[bool] = None
    model_config = ConfigDict(extra="ignore")


class UserResponseSchema(BaseSchema):
{%- if cookiecutter.orm == "sqlalchemy" %}
    id: uuid.UUID
{%- else %}
    id: str = Field(alias="_id")
{%- endif %}
    email: str
    full_name: str
    role: UserRoleEnum
    is_active: bool
    is_platform_admin: bool
    created_at: datetime
    updated_at: datetime
