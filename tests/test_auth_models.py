"""Round-trip ORM values through the migrated SQLite schema."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError

from app.core.refresh_tokens import generate_refresh_token, hash_refresh_token
from app.db.session import Database
from app.models import Credential, ExperienceLevel, RefreshToken, TrainingGoal, User


def new_user(email: str = " Person@Example.COM ") -> User:
    return User(
        email=email,
        first_name="Ada",
        last_name="Lovelace",
        height_cm=Decimal("170.25"),
        weight_kg=Decimal("65.50"),
        experience_level=ExperienceLevel.BEGINNER,
        goal=TrainingGoal.TECHNIQUE,
    )


async def test_profile_round_trip_and_update(migrated_db_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{migrated_db_path}")
    try:
        async with database.session() as session, session.begin():
            user = new_user()
            session.add(user)
            await session.flush()
            user_id = user.id
            assert isinstance(user_id, UUID)
        async with database.session() as session, session.begin():
            stored = await session.get(User, user_id)
            assert stored is not None
            assert stored.email == "person@example.com"
            assert stored.height_cm == Decimal("170.25")
            assert stored.goal is TrainingGoal.TECHNIQUE
            assert stored.created_at.tzinfo == UTC
            before = stored.updated_at
            stored.first_name = "Grace"
        async with database.session() as session, session.begin():
            stored = await session.get(User, user_id)
            assert stored is not None and stored.updated_at >= before
    finally:
        await database.dispose()


async def test_normalized_email_collision(migrated_db_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{migrated_db_path}")
    try:
        async with database.session() as session, session.begin():
            session.add(new_user())
        with pytest.raises(IntegrityError):
            async with database.session() as session, session.begin():
                session.add(new_user("person@example.com"))
    finally:
        await database.dispose()


async def test_token_and_credential_timestamps(migrated_db_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{migrated_db_path}")
    issued = datetime(2026, 9, 21, 8, 0, tzinfo=timezone(timedelta(hours=-5)))
    try:
        async with database.session() as session, session.begin():
            user = new_user()
            session.add(user)
            await session.flush()
            session.add(Credential(user_id=user.id, password_hash="hash"))
            session.add(
                RefreshToken(
                    user_id=user.id,
                    family_id=uuid4(),
                    token_hash=hash_refresh_token(generate_refresh_token()),
                    issued_at=issued,
                    expires_at=issued + timedelta(days=30),
                )
            )
        async with database.session() as session:
            token = (await session.scalars(select(RefreshToken))).one()
            credential = (await session.scalars(select(Credential))).one()
            assert token.issued_at == issued.astimezone(UTC)
            assert token.issued_at.tzinfo == UTC
            assert token.expires_at.tzinfo == UTC
            assert credential.password_updated_at.tzinfo == UTC
    finally:
        await database.dispose()


async def test_naive_timestamp_rejected(migrated_db_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{migrated_db_path}")
    try:
        with pytest.raises(StatementError, match="timezone"):
            async with database.session() as session, session.begin():
                user = new_user()
                user.created_at = datetime(2026, 9, 21)
                session.add(user)
    finally:
        await database.dispose()


def test_opaque_token_material() -> None:
    first, second = generate_refresh_token(), generate_refresh_token()
    assert first != second
    assert len(first) >= 43
    assert len(hash_refresh_token(first)) == 64
    assert hash_refresh_token(first) == hash_refresh_token(first)
    assert hash_refresh_token(first) != hash_refresh_token(second)
    assert first not in hash_refresh_token(first)
