import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        allowed_punctuation = {" ", "'", "’", "-"}
        if any(
            character not in allowed_punctuation
            and unicodedata.category(character)[0] not in {"L", "M"}
            for character in value
        ):
            raise ValueError("Use letters, spaces, apostrophes or hyphens.")
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Enter at least two characters.")
        return normalized


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    role: Literal["customer", "agent", "admin"]
    created_at: datetime


class AuthenticatedResponse(BaseModel):
    user: UserPublic
    csrf_token: str


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserPublic | None = None
    csrf_token: str | None = None
