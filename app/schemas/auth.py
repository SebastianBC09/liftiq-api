"""Explicit auth contracts. Passwords and internal metadata never enter public users."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_serializer,
    field_validator,
)

from app.core.enums import ExperienceLevel, TrainingGoal
from app.schemas.base import ApiModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Measurement = Annotated[Decimal, Field(gt=0, lt=10000, max_digits=6, decimal_places=2)]


class EmailRequest(ApiModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return value.lower()


class Profile(ApiModel):
    first_name: Name
    last_name: Name
    height_cm: Measurement
    weight_kg: Measurement
    experience_level: ExperienceLevel
    goal: TrainingGoal

    @field_serializer("height_cm", "weight_kg", when_used="json")
    def serialize_measurement(self, value: Decimal) -> float:
        return float(value)


class RegisterRequest(Profile, EmailRequest):
    password: SecretStr = Field(min_length=8, max_length=128, repr=False)


class LoginRequest(EmailRequest):
    password: SecretStr = Field(min_length=1, max_length=128, repr=False)


class RefreshRequest(ApiModel):
    refresh_token: SecretStr = Field(min_length=1, max_length=512, repr=False)


class UserResponse(Profile):
    id: UUID
    email: str


class TokenResponse(ApiModel):
    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class AuthResponse(TokenResponse):
    user: UserResponse
