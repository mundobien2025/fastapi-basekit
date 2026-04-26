"""Auth schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    model_config = ConfigDict(extra="ignore")


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshSchema(BaseModel):
    refresh_token: str
    model_config = ConfigDict(extra="ignore")
