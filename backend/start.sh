#!/bin/bash
set -e
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --host 0.0.0.0 --port 3228
