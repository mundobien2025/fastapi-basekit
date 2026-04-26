{% if cookiecutter.orm == "sqlalchemy" -%}
from app.models.auth import Users
from app.models.base import BaseModel

__all__ = ["BaseModel", "Users"]
{%- elif cookiecutter.orm == "beanie" -%}
from app.models.auth import Users

__all__ = ["Users"]
{%- endif %}
