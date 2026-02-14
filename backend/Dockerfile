# syntax=docker/dockerfile:1
# Use BuildKit for cache mounts (faster pip installs on Railway)
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for psycopg2 (layer cached when unchanged)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install production deps only (no pytest); cache pip across builds
COPY requirements-prod.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements-prod.txt

# Copy application code (after deps so code changes don't invalidate pip layer)
COPY . .

# Create data directory (for SQLite mode)
RUN mkdir -p /app/data

# PORT set by Railway; defaults to 8000 for local
ENV PORT=${PORT:-8000}
EXPOSE ${PORT}

# Use entrypoint script (runs migrations for PostgreSQL, then starts uvicorn)
ENTRYPOINT ["bash", "entrypoint.sh"]
