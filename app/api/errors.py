"""Translate domain and framework errors into the public error contract."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.exceptions import ConflictError, EntityNotFoundError, UnauthorizedError


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Only domain messages intended for clients cross the HTTP boundary."""
    if isinstance(exc, UnauthorizedError):
        return JSONResponse(
            status_code=401,
            content={"detail": "Could not validate credentials", "code": "unauthorized"},
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )
    status_code, code = (409, "conflict") if isinstance(exc, ConflictError) else (404, "not_found")
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc), "code": code},
        headers={"Cache-Control": "no-store"},
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return field errors without echoing submitted passwords, tokens, or bodies."""
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"field": list(error["loc"]), "code": error["type"], "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        headers={"Cache-Control": "no-store"},
        content={
            "detail": "Request validation failed",
            "code": "validation_error",
            "errors": errors,
        },
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Normalize framework errors such as missing routes and HTTP bearer failures."""
    assert isinstance(exc, HTTPException)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": f"http_{exc.status_code}"},
        headers={"Cache-Control": "no-store", **(exc.headers or {})},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Keep framework registration outside the domain layer."""
    for error in (EntityNotFoundError, UnauthorizedError, ConflictError):
        app.add_exception_handler(error, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
