#!/bin/bash
set -e

# Ensure data directory for SQLite
mkdir -p backend/data

# Run database migrations (PostgreSQL only)
cd backend
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "Running Alembic migrations..."
    # If tables already exist (created by init_db/create_all) but Alembic
    # has never run, stamp the initial migration so Alembic knows to skip it.
    python -c "
from sqlalchemy import create_engine, inspect
import os, subprocess
engine = create_engine(os.environ['DATABASE_URL'])
tables = inspect(engine).get_table_names()
if 'alembic_version' not in tables and 'teams' in tables:
    print('DB has tables but no alembic_version — stamping initial migration...')
    subprocess.run(['alembic', 'stamp', '2da00d343264'], check=True)
"
    alembic upgrade head
fi

# Start backend on internal port (not exposed to internet)
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready (up to 30s)
echo "Waiting for backend..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "Backend ready!"
    break
  fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "ERROR: Backend process died. Check logs above."
    exit 1
  fi
  sleep 1
done

# Start frontend on Railway's $PORT (exposed to internet)
# Next.js rewrites automatically proxy /api/* → localhost:8000
cd ../frontend
HOSTNAME=0.0.0.0 PORT=${PORT:-3000} npm start
