#!/bin/sh
set -e

echo "=== Context Market — startup ==="

if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL is not set. Add it in Railway → backend service → Variables."
  exit 1
fi

echo "Running migrations..."
python migrate.py

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
