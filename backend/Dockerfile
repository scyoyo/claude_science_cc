FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory (for SQLite mode)
RUN mkdir -p /app/data

# PORT set by Railway; defaults to 8000 for local
ENV PORT=${PORT:-8000}
EXPOSE ${PORT}

# Use entrypoint script (runs migrations for PostgreSQL, then starts uvicorn)
ENTRYPOINT ["bash", "entrypoint.sh"]
