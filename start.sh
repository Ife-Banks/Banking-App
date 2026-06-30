#!/bin/bash
set -e

echo "=== Running database migrations ==="
python3 -c "from alembic.config import main; main(['upgrade', 'head'])"
echo "=== Migrations complete ==="

echo "=== Starting SmartBank server ==="
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"