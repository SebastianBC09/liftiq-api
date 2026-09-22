# LiftIQ API

FastAPI backend for LiftIQ. Pose detection and technique analysis run on the
client; this API will persist users, exercises, favorites, and training sessions.

## Status

Phase one establishes configuration, application lifecycle, SQLite transactions,
security primitives, error handling, tests, and delivery infrastructure.
`GET /health` is the only product endpoint. No domain tables, migration revisions,
or registration/login/refresh/logout endpoints exist yet. The exercise seed
script is still a placeholder.

## Stack

- Python 3.13, FastAPI, Pydantic v2 and pydantic-settings
- SQLAlchemy 2.0 async (`sqlalchemy[asyncio]`), aiosqlite, Alembic
- PyJWT for access tokens; pwdlib with Argon2id for passwords
- uv and a committed lockfile; Ruff, Pyrefly, pytest

## Local setup

```bash
uv sync --locked --all-groups
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
# Put the generated value in SECRET_KEY in .env, replacing the placeholder.
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:create_app --factory --reload
```

Open http://localhost:8000/docs. Configuration is loaded when the application
factory is invoked, not when modules are imported. A missing/invalid secret
fails startup; the example secret is deliberately rejected.

| Setting | Default / requirement |
|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./liftiq.db`; SQLite only, no URL query options |
| `SECRET_KEY` | Required; generate at least 32 random bytes, never commit it |
| `ALGORITHM` | `HS256` only |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 15, positive |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30, positive; reserved for the upcoming auth implementation |
| `ENVIRONMENT` | `development`, `test`, or `production` |
| `BACKEND_CORS_ORIGINS` | JSON array of explicit origins; default `http://localhost:8100` |

For Capacitor, configure the origins actually used by the native app;
`.env.example` includes `capacitor://localhost` and `http://localhost`.
Cross-origin cookie credentials are disabled because the planned native API
uses bearer tokens. Browser refresh-token storage is a separate future decision.

## Architecture and transaction ownership

`Endpoint → Service → Repository → SQLAlchemy → SQLite`

- `app/api/`: routes and HTTP error translation.
- `app/services/`: use cases; no FastAPI or SQLAlchemy imports.
- `app/repositories/`: persistence operations; no independent commits.
- `app/models/`: ORM entities; register models in `app/models/__init__.py` for Alembic.
- `app/schemas/`: explicit request/response models; never serialize credentials.
- `app/core/`: configuration, security primitives, domain exceptions, and HTTP dependency wiring.
- `app/db/`: metadata naming conventions and infrastructure lifecycle.

The application lifespan owns the database engine and disposes it on shutdown.
`get_db` yields a request-scoped session. Session closure rolls back unfinished
work; it never commits implicitly. Use cases will own an explicit unit of work
when repositories/services arrive. Infrastructure implements its transaction
with `session.begin()` (commit on success, rollback on failure).

Every SQLite connection enables foreign keys and a five-second busy timeout.
SQLAlchemy explicitly begins transactions, including reads and DDL, avoiding
SQLite's legacy transaction behavior. Keep transactions short; SQLite permits
only one writer. Do not share a session across concurrent requests/tasks.
SQL parameters are hidden and SQL echo is disabled to avoid credential logging.
Do not enable driver-level debug logs in deployments handling credentials.

## Errors and access-token primitives

Domain errors use `{ "detail": "...", "code": "..." }` with 401, 404, or 409.
Authentication failures include `WWW-Authenticate: Bearer` and a generic message.
Validation failures use 422 with `detail`, `code: "validation_error"`, and an
`errors` array containing `field` (location segments), `code`, and `message`.
Submitted values and Pydantic context are excluded. Validator and domain error
messages must never interpolate passwords, tokens, or other private values.

Access tokens require `sub`, `iat`, `exp`, and `type: "access"`; subjects must be
nonempty strings, and decoding only accepts HS256. Resolving a subject to an
existing user is phase-three work. Password helpers use Argon2id and must be
called outside the event loop when wired into async use cases. Long-lived
refresh tokens, storage, rotation, and revocation are not implemented yet.

## Migrations

```bash
uv run --locked alembic revision --autogenerate -m "describe schema change"
uv run --locked alembic upgrade head
uv run --locked alembic check
```

Review generated revisions, constraints, indexes, and downgrade behavior before
committing. Metadata uses deterministic constraint/index names; CHECK constraints
require explicit names. Alembic is configured for batch operations when SQLite
schema changes require table recreation. Foreign keys stay enabled: migrations
that rebuild referenced tables need deliberate dependency handling and testing.
No application startup path calls `metadata.create_all()`.

Phase one has no revisions, so upgrading creates only Alembic's version table.
Tests exercise the runner on a temporary database; actual schema migration
coverage is added with the domain models in phase two.

## Verification

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pyrefly check app tests
uv run --locked pytest -v
uv run --locked pre-commit install
```

Tests inject settings with dotenv disabled and isolate deployment environment
variables. They cover configuration rejection, JWT claims/signatures/expiry,
password hashing, HTTP errors/CORS/bearer dependencies, application lifecycle,
foreign keys on multiple connections, transaction rollback, transactional DDL,
and Alembic execution from a different working directory.

## Docker and CI

```bash
docker compose up --build
```

The image runs as a non-root user. Compose overrides the local database URL to
`sqlite+aiosqlite:////app/data/liftiq.db` and persists the **directory** in its
`liftiq-data` named volume, including SQLite sidecar files. Normal container
recreation preserves data; `docker compose down -v` deletes it.

The default startup command runs `alembic upgrade head` and starts Uvicorn only
if migration succeeds. This is a single-instance SQLite deployment: before
scaling to multiple instances, move migration execution to a dedicated release
step and reassess the database. `GET /health` reports process liveness, not
migration readiness or database connectivity.

For a standalone container, supply a secret and persistent volume:

```bash
docker build -t liftiq-api .
docker run --env-file .env \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/liftiq.db \
  -e ENVIRONMENT=production \
  -v liftiq-data:/app/data -p 8000:8000 liftiq-api
```

CI installs the committed lockfile and runs lint, format, types, and tests.
Publishing on `main`, `v*` tags, or manual dispatch first calls that same CI
workflow; the image build/push job requires its success. uv is pinned consistently
in CI and Docker, and pre-commit uses the project's locked tool versions.
