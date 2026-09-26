# LiftIQ API

FastAPI backend for LiftIQ. Pose detection and technique analysis run on the
client; this API persists accounts, authentication state, and the exercise catalog.
Favorite and training-session endpoints are future work.

## Status

Phase one establishes configuration, application lifecycle, SQLite transactions,
security primitives, error handling, tests, and delivery infrastructure.
Phase two adds the `users`, `credentials`, and `refresh_tokens` tables and
initial migration `0001`. Phase three implements JSON registration, login, refresh,
logout, and current-user endpoints with transactional services and repositories.
See [the auth contract](docs/auth.md) for payloads and client integration behavior.
Phase four adds a public exercise catalog and an explicit, repeatable seed command.
See [the catalog contract](docs/exercises.md) for filtering and analysis metadata.

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
work; it never commits implicitly. Auth services use the `AuthTransactions` port;
its SQLAlchemy adapter creates a session per transaction and commits once on
success or rolls back on failure. Auth write transactions use `BEGIN IMMEDIATE`
before reading to serialize SQLite writers and avoid deferred lock upgrades.
Login closes its initial read transaction before password verification, then
rechecks credentials in the write transaction. Password work never holds a write lock.

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
existing user happens in the current-user use case. The password adapter runs
Argon2id work in worker threads and verifies a dummy hash for unknown accounts.
Refresh tokens rotate atomically; consumed-token reuse commits family revocation
before returning 401. Logout is idempotent and revokes the associated family.

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

Revision `0001` creates the auth tables. Tests apply the real migration to
temporary databases, check for schema drift, downgrade a populated database,
and re-upgrade. Downgrading to `base` deletes all auth data and is only suitable
for disposable environments or a deliberate restore procedure. Back up the
database before deployment; the downgrade is structural, not data recovery.

`UTCDateTime` is an application conversion type. In generated revisions, render
it as the underlying `sa.DateTime()` so historical migrations do not import
mutable application code. Always review autogeneration output.

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


## Authentication schema

| Table | Purpose and guarantees |
|---|---|
| `users` | UUID identity; unique canonical email; required profile; experience/goal checks; creation/update timestamps |
| `credentials` | User PK/FK enforces at most one password credential; deleting a user cascades to its credential |
| `refresh_tokens` | Unique SHA-256 digest, user/family identifiers, expiry, paired revocation timestamp/reason, optional device info |

ORM email assignment strips surrounding whitespace and lowercases the address;
login uses the same normalization. SQLite also checks trimmed, ASCII-lowercase
storage and email length. Request schemas validate full email syntax. Required names are nonblank and limited to 100 characters.
Height and weight use Decimal/NUMERIC(6,2), with database checks for positive
values below 10,000 and at most two decimal places. These are storage limits;
product-specific input ranges will be validated separately.

Timestamps reject naive Python datetimes, normalize aware input to UTC, and
restore UTC timezone information on load. SQLite stores naive UTC values.
Database defaults set creation timestamps; ORM updates maintain `updated_at`.
Raw SQL updates must explicitly update that field. Changing a password must
explicitly update `password_updated_at` in the future service transaction.

Refresh tokens use 32 random bytes encoded with URL-safe base64. Only their
64-character lowercase SHA-256 digest belongs in the table; password hashes
continue to use Argon2id. No raw-token column exists. Expiration must follow
issuance. Revocation time and reason must either both be absent or both be
present; allowed reasons are `rotated`, `logout`, and `reuse`.

The `(user_id, family_id)` index supports user-scoped family operations and user
lookups; unique constraints index email and token digest without redundant
indexes. Services must preserve the same family across rotation, scope family
operations by user, and retain consumed tokens for reuse detection. These
behaviors are implemented by the auth use cases, not the table alone.

Credentials and tokens cascade on user deletion. No implicit ORM relationship
loading is configured: repositories query explicitly. The FK permits a user
to temporarily exist without credentials; the registration use case enforces
creation of all three records in one transaction. Integration tests already
verify that a failed token insert can roll back the entire transaction.
