#!/usr/bin/env python3
"""
Run database migrations using asyncpg.
Executes each SQL file as a single string — handles PL/pgSQL $$ blocks correctly.
"""
import asyncio
import asyncpg
import os
import sys
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "")

MIGRATIONS = [
    "migrations/001_init.sql",
    "migrations/002_agent_verification.sql",
    "migrations/003_buyer_reputation.sql",
    "migrations/004_transactions.sql",
]


async def run():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set.")
        sys.exit(1)

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"ERROR: Could not connect: {e}")
        sys.exit(1)

    print("Connected.\n")

    try:
        for migration_file in MIGRATIONS:
            path = Path(migration_file)
            if not path.exists():
                print(f"SKIP  {migration_file} (not found)")
                continue

            sql = path.read_text()
            print(f"Applying {migration_file}...")
            try:
                await conn.execute(sql)
                print(f"  OK\n")
            except asyncpg.DuplicateTableError:
                print(f"  Already applied (tables exist)\n")
            except asyncpg.DuplicateObjectError:
                print(f"  Already applied (objects exist)\n")
            except Exception as e:
                # Log but keep going — partial migrations are better than none
                print(f"  WARN: {str(e)[:200]}\n")

    finally:
        await conn.close()

    print("=== Migrations complete ===\n")


if __name__ == "__main__":
    asyncio.run(run())
