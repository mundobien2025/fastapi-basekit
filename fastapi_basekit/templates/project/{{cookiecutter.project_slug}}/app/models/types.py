{% if cookiecutter.orm == "sqlalchemy" -%}
"""Custom SQLAlchemy column types."""

from enum import Enum
from uuid import UUID

from sqlalchemy.types import String, TypeDecorator


class GUID(TypeDecorator):
    """Stores UUID as 36-char string; returns uuid.UUID in Python."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, str):
            return str(UUID(value))
        raise TypeError(f"Cannot serialize {type(value)!r} as UUID")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(value)


class LowercaseEnum(TypeDecorator):
    """Stores enum values as their lowercase string representation."""

    impl = String
    cache_ok = True

    def __init__(self, enum_class: type[Enum], length: int = 50):
        super().__init__(length=length)
        self.enum_class = enum_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value.lower()
        return str(value).lower()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum_class(value)
{%- else -%}
# Beanie projects don't need custom types — placeholder.
{%- endif %}
