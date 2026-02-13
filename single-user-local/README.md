# Virtual Lab - Single User Local Version

Single-user local version for rapid feature development and testing.

## Features

- ✅ No user registration/login required
- ✅ SQLite local database
- ✅ Docker Compose one-click startup
- ✅ Suitable for personal use and feature validation

## Quick Start

```bash
# Start services
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Documentation: http://localhost:8000/docs

# Stop services
docker-compose down

# Clear data (reset database)
rm backend/data/virtuallab.db
```

## Tech Stack

- Backend: FastAPI + SQLite
- Frontend: Next.js + React
- Deployment: Docker Compose

## Data Storage

All data is stored in the `backend/data/virtuallab.db` SQLite file.

## Development

```bash
# Run backend tests
docker-compose exec backend pytest tests/ -v

# Run backend with coverage
docker-compose exec backend pytest tests/ -v --cov=app
```

## Project Structure

```
single-user-local/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/          # Database models
│   │   ├── api/             # API endpoints
│   │   ├── schemas/         # Pydantic schemas
│   │   └── core/            # Core business logic
│   ├── tests/               # Tests
│   ├── data/                # SQLite database
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```
