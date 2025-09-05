from pydantic import BaseModel


class TokenSchema(BaseModel):
    sub: str
    exp: int
