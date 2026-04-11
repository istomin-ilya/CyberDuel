# CyberDuel

P2P + Pool prediction market protocol for esports outcomes.

## What Is Implemented

- Backend: FastAPI + SQLAlchemy + Alembic
- Modes:
  - P2P direct order book
  - Pool market (DeFi-style liquidity pool with proportional payouts)
- Auth: register/login/refresh/me (JWT)
- Escrow and transaction audit trail
- Settlement flows:
  - Optimistic Oracle integration for match resolution
  - P2P settlement (claims, disputes, admin resolution)
  - Pool settlement with proportional payouts
- Frontend: React + TypeScript + Vite + Zustand
- Containerized local stack via Docker Compose

## Repository Layout

- backend: API, models, business services, migrations, tests
- frontend: React client application
- docker-compose.yml: local full-stack orchestration

## Quick Start (Docker, Recommended)

1. Create env file in repo root:

```bash
cp .env.example .env
```

2. Start stack:

```bash
docker compose up --build
```

3. Open apps:

- Frontend: http://localhost:5173
- Backend API: http://localhost:3228
- API docs: http://localhost:3228/docs

Notes:
- Frontend container uses Nginx reverse proxy for /api to backend.
- Backend container runs migrations on startup via backend/start.sh.

## Quick Guide (Working Features)

1. Start:

```bash
docker compose up --build
```

2. On backend startup:
- migrations are applied
- seed is executed
- seed credentials are written to the `data` folder

3. Useful URLs:
- Main frontend: http://localhost:5173
- Admin page: http://localhost:5173/admin.html
- API docs: http://localhost:3228/docs

4. Admin access:
- use Quick Admin Login on `admin.html`

5. Stable now:
- Events: create + status transitions
- Markets: create + status transitions
- Settlement: dispute resolve + market settle
- Auth: login/refresh/me

6. Current limitations:
- global `/api/users` endpoint is not implemented
- users deposit action is disabled in admin UI (backend endpoint is missing)

## Local Development (Without Docker)

## Prerequisites

- Python 3.12+
- Node.js 20+
- uv (recommended for Python deps)

## Backend

1. Create backend env file at backend/.env (this is where app config reads from):

```bash
cp backend/app/.env.example backend/.env
```

2. Install dependencies:

```bash
cd backend
uv sync
```

3. Run migrations:

```bash
uv run alembic upgrade head
```

4. Start API:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 3228
```

## Frontend

1. Create frontend env file:

```bash
cp frontend/.env.example frontend/.env
```

2. Install and run:

```bash
cd frontend
npm install
npm run dev
```

3. Open:

- Frontend: http://localhost:5173

Important for local frontend:
- frontend/.env should point VITE_API_URL to backend, for example:
  - VITE_API_URL=http://localhost:3228

## Build

## Frontend production build

```bash
cd frontend
npm run build
```

## Backend package install check

```bash
cd backend
uv sync
```

## Testing

Backend tests are located in backend/tests.

Recommended command:

```bash
cd backend
uv run pytest -q
```

## Main API Groups

- Auth:
  - /auth/register
  - /auth/login
  - /auth/refresh
  - /auth/me
- Events:
  - /api/events
- Markets:
  - /api/markets
- Orders:
  - /api/orders
- Settlement:
  - /api/settlement
- Pool markets:
  - /api/pool-markets
- Transactions:
  - /api/transactions
- Admin:
  - /api/admin

## Configuration

Main backend settings live in backend/app/config.py and are loaded from backend/.env.

Key variables:

- DATABASE_URL
- JWT_SECRET
- JWT_ALGORITHM
- ACCESS_TOKEN_EXPIRE_MINUTES
- REFRESH_TOKEN_EXPIRE_DAYS
- CORS_ORIGINS
- ORACLE_PROVIDER

## Security Note

This project currently includes development defaults and demo balances. Treat current config as development-grade, not production-hardened.

## Current Version

- Version: 0.1.0
- Last updated: 2026-03-20
