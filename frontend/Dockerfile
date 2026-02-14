FROM node:20-slim AS base

# --- Dependencies stage ---
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# --- Build stage ---
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# BACKEND_URL baked into rewrites at build time
# Local docker-compose: http://backend:8000
# Railway: http://<service>.railway.internal:8000
ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL

RUN npm run build

# --- Production stage ---
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

# Standalone output: minimal footprint (~100MB vs ~500MB)
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

ENV HOSTNAME="0.0.0.0"
# PORT is set by Railway (usually 8080); defaults to 3000 for local
ENV PORT=${PORT:-3000}
EXPOSE ${PORT}

CMD ["node", "server.js"]
