# CyberDuel — Demo Runbook (Docker-only)

This guide is designed to run on any computer using Docker Compose only.

## Prerequisites

- Docker Desktop (or Docker Engine) with Compose v2
- Free ports: 5173 (frontend) and 3228 (backend)

## Start

From the repository root:

1) Build and run:

docker compose up --build

2) Open:

- Frontend: http://localhost:5173
- Admin Console: http://localhost:5173/admin.html
- Backend API docs: http://localhost:3228/docs

## Reset demo data (recommended before presenting)

Note: this repository is configured to reset+seed automatically on backend container start (`SEED_RESET_ON_START=true`).
You can still run a manual reset at any time:

This truncates all tables and re-seeds the deterministic demo dataset.

docker compose exec backend python scripts/seed.py --reset

## Demo accounts

- Admin: admin@cyberduel.gg / admin12345
- Users: user1@cyberduel.gg … user5@cyberduel.gg / user12345

## Seeded fixtures (what to use in the demo)

After reset seed the database contains:

- 6 events, 6 markets, 12 outcomes
- 3 pool markets + 3 P2P markets
- 12 open P2P orders
- 15 pool bets

Use these matchups (team names) rather than relying on IDs:

- Pool mode: NaVi vs G2; Vitality vs Astralis; Team Spirit vs OG
- P2P mode: Liquid vs Tundra; T1 vs Gen.G; Sentinels vs LOUD

## Main live script (8–12 minutes)

### A) Admin setup (2–3 min)

1) Open Admin Console: http://localhost:5173/admin.html
2) Quick Admin Login:
   - Email: admin@cyberduel.gg
   - Password: admin12345
3) Confirm Events and Markets load.

### B) P2P flow (3–5 min)

1) Open frontend: http://localhost:5173
2) Login as user1@cyberduel.gg
3) Go to P2P page
4) Pick “T1 vs Gen.G”
5) Create an order (example): outcome=T1, amount=50, odds=1.80
6) In another tab login as user2@cyberduel.gg
7) Match the order
8) Show a contract exists and balances changed

### C) Settle the market via Admin (2–3 min)

1) Admin Console → Settlement
2) Select event → market → winning outcome
3) Click “Settle Market”
4) Show settlement result

### D) Pool flow (2–3 min)

1) Frontend → Pool page
2) Pick “NaVi vs G2”
3) Place a small bet (20–30)
4) Show pool state update (total pool + estimated odds)
5) Optional: settle via Admin Console (same Settlement section)

## Fallbacks

- If you get 401/auth issues: re-login (admin + users).
- If data looks wrong: run the reset seed command again.
- If UI is slow: demonstrate the same calls via Swagger (/docs).

## Stop / cleanup

- Stop containers: docker compose down
- Full cleanup (also clears the persisted sqlite volume): docker compose down -v
