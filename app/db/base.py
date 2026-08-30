"""Declarative base + central import point for all ORM models.

Alembic's autogenerate needs every model imported somewhere that it scans,
so as models are added under app/models/, import them here too.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


# from app.models.user import User  # noqa: F401
# from app.models.exercise import Exercise  # noqa: F401
# from app.models.session import Session  # noqa: F401
# from app.models.user_favorite import UserFavorite  # noqa: F401
