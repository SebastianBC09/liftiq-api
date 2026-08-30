# LiftIQ API

Backend for **LiftIQ**, a mobile app that analyzes weightlifting technique in
real time using on-device pose detection (BlazePose). This service persists
users, the exercise catalog, favorites, and training sessions, and serves
them to the [Ionic/Angular frontend](../liftiq-app) over a REST API. It does
**not** process video or run any computer vision — that happens entirely on
the client.

See `/docs` in the project workspace for the full product spec and
architecture/standards documents this scaffold implements.

## Stack

- **FastAPI** (async, layered architecture: endpoints → services → repositories)
- **SQLAlchemy 2.x** (async, SQLite via `aiosqlite`) + **Alembic** migrations
- **Pydantic v2** / `pydantic-settings` for typed config
- **JWT** (`python-jose`) + **Argon2** password hashing (`pwdlib`)
- **uv** for dependency management, **Ruff** for lint/format, **Pyrefly** for type checking
- **pytest** + `pytest-asyncio` + `httpx.AsyncClient` for testing

## Getting started

```bash
# 1. Install dependencies (creates .venv automatically)
uv sync --all-groups

# 2. Configure environment
cp .env.example .env
# then set SECRET_KEY to a random 64-char string, e.g.:
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Run the app
uv run uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

## Common commands

| Task | Command |
|---|---|
| Run dev server | `uv run uvicorn app.main:app --reload` |
| Run tests | `uv run pytest -v` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run pyrefly check app tests` |
| New migration | `uv run alembic revision --autogenerate -m "message"` |
| Apply migrations | `uv run alembic upgrade head` |
| Install git hooks | `uv run pre-commit install` |

## Project structure

```
app/
├── main.py             # FastAPI() instance, CORS, router registration
├── api/v1/              # HTTP layer — endpoints only, no business logic
├── services/            # Business logic — no FastAPI or SQLAlchemy imports
├── repositories/        # Only layer that talks to SQLAlchemy
├── models/               # SQLAlchemy ORM models
├── schemas/              # Pydantic Create/Update/Response schemas per entity
├── core/                 # Settings, JWT/hashing, shared Depends(), exceptions
└── db/                    # Declarative base + async engine/session factory
```

Request flow is always `Endpoint → Service → Repository → SQLAlchemy → SQLite`,
never the reverse. See `../docs/LiftIQ-architecture-and-standards.md` for the
full rationale (SOLID mapping, naming conventions, testing requirements).

## Docker

```bash
docker build -t liftiq-api .
docker run -p 8000:8000 --env-file .env liftiq-api
# or:
docker compose up --build
```

On every push to `main` (and on `v*` tags), GitHub Actions builds and pushes
an image to GHCR:

```bash
docker pull ghcr.io/<owner>/liftiq-api:main
```

The first time this runs, the package may be created as **private** by
default — go to the package settings on GitHub and set it to public if you
need to pull it without authenticating during a class session.

## Status

This is the initial scaffold: folder structure, config, Docker, and CI are
wired up, but no domain models or endpoints exist yet. Next step is
implementing `auth` (register/login) end to end through all four layers.
