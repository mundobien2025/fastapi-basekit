{% if cookiecutter.orm == "sqlalchemy" -%}
"""Users model."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import UserRoleEnum
from app.models.types import LowercaseEnum


class Users(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(
        LowercaseEnum(UserRoleEnum, length=20),
        nullable=False,
        server_default="user",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
{%- elif cookiecutter.orm == "beanie" -%}
"""Users document."""

from pydantic import EmailStr, Field

from app.models.base import CustomBaseModel
from app.models.enums import UserRoleEnum


class Users(CustomBaseModel):
    email: EmailStr
    password_hash: str
    full_name: str
    role: UserRoleEnum = UserRoleEnum.user
    is_active: bool = True
    is_platform_admin: bool = False

    class Settings:
        name = "users"
        indexes = [
            "email",
        ]
{%- endif %}
