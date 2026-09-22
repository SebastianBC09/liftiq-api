"""OpenAPI models for the error responses emitted by the HTTP boundary."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    code: str


class FieldError(BaseModel):
    field: list[str | int]
    code: str
    message: str


class ValidationErrorResponse(ErrorResponse):
    errors: list[FieldError]
