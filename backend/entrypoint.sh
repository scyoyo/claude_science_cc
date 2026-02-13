#!/bin/bash
set -e

# Run Alembic migrations (only for PostgreSQL; skip for SQLite)
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
