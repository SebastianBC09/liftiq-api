"""Seed a migrated database: uv run python -m scripts.seed_exercises."""

import asyncio

from app.core.config import Settings
from app.data.catalog import load_catalog
from app.db.session import Database
from app.repositories.exercises import SqlAlchemyExerciseRepository


async def seed(settings: Settings) -> int:
    catalog = load_catalog()
    database = Database(settings.database_url)
    try:
        async with database.session() as session, session.begin():
            await session.connection(execution_options={"sqlite_write": True})
            await SqlAlchemyExerciseRepository(session).seed(catalog)
    finally:
        await database.dispose()
    return len(catalog)


def main() -> None:
    print(f"Seeded {asyncio.run(seed(Settings()))} exercises")


if __name__ == "__main__":
    main()
