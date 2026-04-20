#!/bin/bash
set -e
alembic upgrade head

# Optional: reset DB on container start (useful for repeatable demos)
# Enable via env: SEED_RESET_ON_START=true (or 1/yes), or RESET_DB_ON_START=true
RESET_ON_START="${SEED_RESET_ON_START:-${RESET_DB_ON_START:-}}"
case "$RESET_ON_START" in
	1|true|TRUE|yes|YES)
		echo "[start.sh] Resetting DB + seeding (SEED_RESET_ON_START enabled)"
		python scripts/seed.py --reset
		;;
	*)
		echo "[start.sh] Seeding (idempotent)"
		python scripts/seed.py
		;;
esac

uvicorn app.main:app --host 0.0.0.0 --port 3228
