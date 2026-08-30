"""Domain-level exceptions and their FastAPI handlers.

Services raise these; they never raise HTTPException directly, which keeps the
service layer free of any FastAPI/HTTP knowledge (see architecture doc, section 3.3).
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class EntityNotFoundError(Exception):
    """Raised when a repository lookup finds no matching row."""

    def __init__(self, entity: str, entity_id: int | str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} {entity_id} not found")


class UnauthorizedError(Exception):
    """Raised when a request lacks valid credentials or permissions."""


async def entity_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert EntityNotFoundError into a 404 JSON response.

    Typed as `Exception` to match Starlette's `add_exception_handler` signature;
    FastAPI only ever dispatches this handler for `EntityNotFoundError` instances.
    """
    assert isinstance(exc, EntityNotFoundError)
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def unauthorized_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert UnauthorizedError into a 401 JSON response.

    Typed as `Exception` to match Starlette's `add_exception_handler` signature;
    FastAPI only ever dispatches this handler for `UnauthorizedError` instances.
    """
    assert isinstance(exc, UnauthorizedError)
    return JSONResponse(status_code=401, content={"detail": str(exc)})
