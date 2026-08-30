"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    EntityNotFoundError,
    UnauthorizedError,
    entity_not_found_handler,
    unauthorized_handler,
)

settings = get_settings()

app = FastAPI(title="LiftIQ API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(EntityNotFoundError, entity_not_found_handler)
app.add_exception_handler(UnauthorizedError, unauthorized_handler)

app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Basic liveness check used by Docker/CI and manual smoke tests."""
    return {"status": "ok"}
