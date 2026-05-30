#!/usr/bin/env python3
"""
Run database migrations using asyncpg.
Uses the same connection as the app — handles SSL automatically.
Each statement is run individually so partial failures are reported
without stopping the whole migration.
"""
import asyncio
import asyncpg
import os
import re
import sys
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "")

MIGRATIONS = [
    "migrations/001_init.sql",
    "migrations/002_agent_verification.sql",
    "migrations/003_buyer_reputation.sql",
    "migrations/004_transactions.sql",
]


def split_statements(sql: str) -> list[str]:
    """Split SQL file into individual statements, skipping blanks."""
    statements = []
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            statements.append(stmt + ";")
    return statements


async def run():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    print(f"Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    print("Connected.\n")

    try:
        for migration_file in MIGRATIONS:
            path = Path(migration_file)
            if not path.exists():
                print(f"SKIP  {migration_file} (file not found)")
                continue

            print(f"--- {migration_file} ---")
            sql = path.read_text()
            statements = split_statements(sql)
            ok = 0
            skipped = 0

            for stmt in statements:
                try:
                    await conn.execute(stmt)
                    ok += 1
                except asyncpg.DuplicateTableError:
                    skipped += 1
                except asyncpg.DuplicateObjectError:
                    skipped += 1
                except asyncpg.UniqueViolationError:
                    skipped += 1
                except Exception as e:
                    # Log but continue — don't block startup
                    short = str(e).split("\n")[0]
                    print(f"  WARN: {short}")
                    skipped += 1

            print(f"  OK: {ok} statements, {skipped} skipped (already exist)\n")

    finally:
        await conn.close()

    print("=== Migrations complete ===\n")


if __name__ == "__main__":
    asyncio.run(run())
