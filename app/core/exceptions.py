"""Domain exceptions. This module deliberately has no HTTP dependencies."""


class EntityNotFoundError(Exception):
    """An entity requested by a use case does not exist."""

    def __init__(self, entity: str, entity_id: int | str) -> None:
        super().__init__(f"{entity} {entity_id} not found")


class UnauthorizedError(Exception):
    """Credentials are missing or invalid."""


class ConflictError(Exception):
    """A use case conflicts with existing state."""
