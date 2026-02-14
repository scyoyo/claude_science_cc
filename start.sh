#!/bin/bash
set -e

# Ensure data directory for SQLite
mkdir -p backend/data

# Start backend on internal port (not exposed to internet)
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &

# Start frontend on Railway's $PORT (exposed to internet)
# Next.js rewrites automatically proxy /api/* → localhost:8000
cd ../frontend
HOSTNAME=0.0.0.0 PORT=${PORT:-3000} npm start
