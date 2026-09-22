"""Application factory. Run with `uvicorn app.main:create_app --factory`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.v1.router import api_router
from app.core.config import Settings
from app.db.session import Database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Create infrastructure at startup and always release it at shutdown."""
    database = Database(app.state.settings.database_url)
    app.state.database = database
    try:
        yield
    finally:
        await database.dispose()


async def health_check() -> dict[str, str]:
    """Liveness only: this does not claim database or migration readiness."""
    return {"status": "ok"}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct an isolated application without creating tables or connections."""
    settings = settings if settings is not None else Settings()
    app = FastAPI(title="LiftIQ API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    app.add_api_route("/health", health_check, tags=["health"])
    return app
