#!/bin/sh
set -e

echo "=== Running database migrations ==="
for migration in \
    migrations/001_init.sql \
    migrations/002_agent_verification.sql \
    migrations/003_buyer_reputation.sql \
    migrations/004_transactions.sql
do
    echo "Applying $migration..."
    psql "$DATABASE_URL" -f "$migration"
    echo "Done: $migration"
done

echo "=== Migrations complete. Starting server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
