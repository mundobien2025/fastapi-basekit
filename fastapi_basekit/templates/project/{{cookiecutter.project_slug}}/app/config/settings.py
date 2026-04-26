"""Application settings."""

import os
from functools import lru_cache
from typing import Annotated, List, Optional

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v):
    if isinstance(v, str):
        return [o.strip() for o in v.split(",") if o.strip()]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if not os.environ.get("RUNNING_IN_DOCKER") else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "{{ cookiecutter.project_name }}"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "{{ cookiecutter.description }}"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: Annotated[List[str], BeforeValidator(parse_cors)] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    DATABASE_URL: str
{% if cookiecutter.orm == "beanie" %}    DATABASE_NAME: str = "{{ cookiecutter.package_name }}"
{% endif %}
    ENVIRONMENT: str = "local"
    DEBUG: bool = True

{% if cookiecutter.cache == "redis" %}    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
{% endif %}
{% if cookiecutter.bucket == "s3" %}    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION_NAME: str = "us-east-1"
    AWS_S3_BUCKET_NAME: Optional[str] = None
{% endif %}
    UPLOAD_DIR: str = "uploads"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
