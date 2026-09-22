#!/bin/sh
# Single-instance SQLite deployment: fail closed if migration fails.
set -eu
alembic upgrade head
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
