#!/bin/bash
set -e

# Run Alembic migrations (only for PostgreSQL; skip for SQLite)
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

# Start the application (PORT set by Railway, defaults to 8000)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
