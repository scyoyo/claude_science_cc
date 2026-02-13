# Virtual Lab V2 - Architecture Plan

## Overview

V2 evolves the single-user local app into a multi-user cloud-ready platform while maintaining backward compatibility with V1's SQLite-based deployment.

## V2 Goals

1. **Multi-user support** with authentication and authorization
2. **PostgreSQL** for production database (SQLite remains for dev/single-user)
3. **Redis** for caching, rate limiting, and session management
4. **WebSocket** for real-time meeting updates
5. **Production Docker Compose** with Nginx reverse proxy
6. **Kubernetes-ready** container architecture

---

## Architecture Diagram

```
                    ┌─────────────┐
                    │   Nginx     │ :80/:443
                    │   Reverse   │
                    │   Proxy     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼──┐   ┌────▼───┐  ┌────▼────┐
        │Frontend│   │Backend │  │WebSocket│
        │Next.js │   │FastAPI │  │FastAPI  │
        │ :3000  │   │ :8000  │  │ :8001   │
        └────────┘   └───┬────┘  └────┬────┘
                         │            │
              ┌──────────┼────────────┤
              │          │            │
        ┌─────▼──┐  ┌───▼────┐  ┌───▼───┐
        │Postgres│  │ Redis  │  │ MinIO │
        │  :5432 │  │ :6379  │  │ :9000 │
        └────────┘  └────────┘  └───────┘
```

---

## Phase 2.1: Multi-User Authentication

### Tech Choice: FastAPI + JWT + OAuth2

```
New files:
  backend/app/models/user.py          # User model
  backend/app/schemas/user.py         # User schemas
  backend/app/api/auth.py             # Login/register/refresh endpoints
  backend/app/core/auth.py            # JWT token creation/validation
  backend/app/core/permissions.py     # RBAC permission checks
  backend/app/middleware/auth.py      # Auth middleware
```

### User Model
```python
class User:
    id: UUID
    email: str (unique)
    username: str (unique)
    hashed_password: str
    is_active: bool
    is_admin: bool
    created_at: datetime

class UserTeamRole:
    user_id: FK(User)
    team_id: FK(Team)
    role: "owner" | "editor" | "viewer"
```

### Auth Endpoints
```
POST /api/auth/register     # Create account
POST /api/auth/login        # Get JWT token pair
POST /api/auth/refresh      # Refresh access token
GET  /api/auth/me           # Current user info
POST /api/auth/oauth/{provider}  # OAuth login (GitHub, Google)
```

### Authorization Rules
- Teams: owner can delete, editors can modify, viewers read-only
- Agents: inherit team permissions
- Meetings: team members can view, editors+ can run
- API Keys: per-user, encrypted with user-specific salt

---

## Phase 2.2: Database Migration to PostgreSQL

### Strategy: Alembic migrations + dual DB support

```
New files:
  backend/alembic/              # Alembic migrations directory
  backend/alembic.ini           # Alembic config
  backend/app/database.py       # Updated for Postgres support
```

### Config Changes
```python
# config.py - auto-detect database
DATABASE_URL: str = "sqlite:///./data/virtuallab.db"  # Default (V1 compat)
# Override with: DATABASE_URL=postgresql://user:pass@localhost/virtuallab
```

### Migration Plan
1. Add Alembic with `alembic init`
2. Generate initial migration from existing models
3. All model changes go through Alembic migrations
4. SQLite remains default for local dev
5. PostgreSQL for docker-compose and production

---

## Phase 2.3: Redis Integration

### Use Cases
- **Session store**: JWT refresh token blocklist
- **Rate limiting**: per-user LLM API rate limits
- **Cache**: Team/agent data caching for read-heavy pages
- **Pub/Sub**: Real-time meeting message broadcasting

```
New files:
  backend/app/core/redis.py         # Redis connection manager
  backend/app/core/rate_limiter.py  # Rate limiting middleware
  backend/app/core/cache.py         # Caching decorator
```

---

## Phase 2.4: WebSocket for Real-Time Updates

### Scope: Meeting execution with live streaming

```
New files:
  backend/app/api/ws.py             # WebSocket endpoint
  backend/app/core/meeting_ws.py    # WS meeting runner
  frontend/src/hooks/useWebSocket.ts
  frontend/src/components/MeetingLive.tsx
```

### Protocol
```
WS /api/ws/meetings/{meeting_id}

Client -> Server: { "type": "start_round", "rounds": 1 }
Server -> Client: { "type": "agent_speaking", "agent_name": "Dr. X" }
Server -> Client: { "type": "message", "agent_name": "Dr. X", "content": "..." }
Server -> Client: { "type": "round_complete", "round": 1 }
```

---

## Phase 2.5: Production Docker Compose

### docker-compose.prod.yml

```yaml
services:
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on: [frontend, backend]

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://virtuallab:${DB_PASSWORD}@postgres/virtuallab
      - REDIS_URL=redis://redis:6379/0
      - ENCRYPTION_SECRET=${ENCRYPTION_SECRET}
      - JWT_SECRET=${JWT_SECRET}
    depends_on: [postgres, redis]

  frontend:
    build: ./frontend
    environment:
      - NEXT_PUBLIC_API_URL=/api

  postgres:
    image: postgres:16-alpine
    volumes: [postgres-data:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=virtuallab
      - POSTGRES_USER=virtuallab
      - POSTGRES_PASSWORD=${DB_PASSWORD}

  redis:
    image: redis:7-alpine
    volumes: [redis-data:/data]

volumes:
  postgres-data:
  redis-data:
```

### Nginx Config
```
/ -> frontend:3000
/api -> backend:8000
/api/ws -> backend:8000 (WebSocket upgrade)
```

---

## Phase 2.6: Kubernetes Migration Path

### Resources
```
k8s/
  namespace.yaml
  backend/
    deployment.yaml     # 2+ replicas, HPA
    service.yaml
    configmap.yaml
  frontend/
    deployment.yaml
    service.yaml
  postgres/
    statefulset.yaml
    service.yaml
    pvc.yaml
  redis/
    deployment.yaml
    service.yaml
  ingress.yaml          # Nginx Ingress Controller
  secrets.yaml          # Sealed Secrets
```

### Key Considerations
- Stateless backend (sessions in Redis, not memory)
- Horizontal scaling with HPA (CPU/memory targets)
- PostgreSQL with persistent volume claims
- Redis for shared state between backend replicas
- Sealed Secrets for credential management
- Ingress with TLS termination

---

## Implementation Priority

| Phase | Feature | Effort | Dependencies |
|-------|---------|--------|--------------|
| 2.1 | Authentication | Medium | None |
| 2.2 | PostgreSQL + Alembic | Medium | None |
| 2.3 | Redis | Small | 2.1 (for sessions) |
| 2.4 | WebSocket | Medium | None |
| 2.5 | Prod Docker Compose | Small | 2.1, 2.2, 2.3 |
| 2.6 | Kubernetes | Large | 2.5 |

### Recommended Order
1. **2.1 + 2.2** in parallel (auth + postgres)
2. **2.3** Redis (rate limiting + sessions)
3. **2.4** WebSocket (real-time meetings)
4. **2.5** Production Docker Compose
5. **2.6** Kubernetes (when needed)

---

## New Dependencies (V2)

```
# Backend additions
alembic>=1.13                # Database migrations
asyncpg>=0.30                # Async PostgreSQL driver
psycopg2-binary>=2.9         # PostgreSQL adapter
redis>=5.0                   # Redis client
python-jose[cryptography]    # JWT tokens
passlib[bcrypt]              # Password hashing
python-multipart             # Form data (login)
websockets>=12.0             # WebSocket support
```

---

## Backward Compatibility

V2 maintains full V1 compatibility:
- SQLite still works as default for single-user local mode
- All V1 API endpoints remain unchanged
- Auth is optional (disabled by default for V1 mode)
- V1 docker-compose.yml untouched; V2 uses docker-compose.prod.yml
- Environment variable `AUTH_ENABLED=false` skips auth middleware
