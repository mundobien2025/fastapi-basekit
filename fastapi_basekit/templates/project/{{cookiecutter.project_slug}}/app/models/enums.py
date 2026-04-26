"""Domain enums."""

import enum


class UserRoleEnum(str, enum.Enum):
    admin = "admin"
    user = "user"
