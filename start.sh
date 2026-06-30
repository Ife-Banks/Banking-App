#!/bin/bash
set -e

echo "=== Running database migrations ==="
python -m alembic upgrade head

echo "=== Starting SmartBank server ==="
python -m uvicorn app.main:app --host 0.0.0.0 --port 10000