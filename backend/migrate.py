#!/usr/bin/env python3
"""
Database migration runner.
Prints verbose output so Railway logs show exactly what happened.
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


def split_sql(sql: str) -> list:
    """
    Split SQL into individual statements, correctly handling
    PL/pgSQL $$ dollar-quoted blocks (which contain semicolons).
    """
    statements = []
    current = ""
    in_dollar_quote = False
    i = 0

    while i < len(sql):
        # Toggle dollar-quote mode on $$
        if sql[i:i+2] == "$$":
            in_dollar_quote = not in_dollar_quote
            current += "$$"
            i += 2
            continue

        # Statement boundary — only outside dollar quotes
        if sql[i] == ";" and not in_dollar_quote:
            current += ";"
            stmt = current.strip()
            # Skip blank lines and pure comments
            non_comment = "\n".join(
                l for l in stmt.splitlines() if not l.strip().startswith("--")
            ).strip()
            if non_comment and non_comment != ";":
                statements.append(stmt)
            current = ""
            i += 1
            continue

        current += sql[i]
        i += 1

    remaining = current.strip()
    if remaining:
        statements.append(remaining)

    return statements


async def table_exists(conn, name: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=$1)", name
    )


async def run():
    # ── Diagnostics ────────────────────────────────────────────
    print("=" * 50)
    print("MIGRATION RUNNER")
    print("=" * 50)
    print(f"DATABASE_URL : {'SET' if DATABASE_URL else 'NOT SET'}")
    for f in MIGRATIONS:
        p = Path(f)
        status = f"{p.stat().st_size}B" if p.exists() else "MISSING"
        print(f"  {f} : {status}")
    print()

    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set — add it to Railway backend Variables.")
        sys.exit(1)

    # ── Connect ────────────────────────────────────────────────
    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        version = await conn.fetchval("SELECT version()")
        print(f"Connected: {version[:60]}\n")
    except Exception as e:
        print(f"ERROR: Cannot connect to database: {e}")
        sys.exit(1)

    try:
        # ── Check existing state ───────────────────────────────
        agents_exist = await table_exists(conn, "agents")
        print(f"Table 'agents' already exists: {agents_exist}")
        if agents_exist:
            count = await conn.fetchval("SELECT COUNT(*) FROM agents")
            print(f"  Rows in agents: {count}")
        print()

        # ── pgvector extension (handle separately) ─────────────
        print("Installing pgvector extension...")
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("  pgvector: OK\n")
        except Exception as e:
            print(f"  pgvector WARNING: {e}")
            print("  Vector search will not work without pgvector.\n")

        # ── Run each migration ─────────────────────────────────
        for migration_file in MIGRATIONS:
            path = Path(migration_file)
            if not path.exists():
                print(f"SKIP {migration_file} — file not found")
                continue

            sql = path.read_text()

            # Remove the CREATE EXTENSION line — handled above
            sql_lines = [
                l for l in sql.splitlines()
                if "CREATE EXTENSION" not in l
            ]
            sql_clean = "\n".join(sql_lines)

            statements = split_sql(sql_clean)
            print(f"--- {migration_file} ({len(statements)} statements) ---")

            ok = skipped = errors = 0
            for stmt in statements:
                try:
                    await conn.execute(stmt)
                    ok += 1
                except (
                    asyncpg.DuplicateTableError,
                    asyncpg.DuplicateObjectError,
                    asyncpg.UniqueViolationError,
                ) as e:
                    skipped += 1
                except asyncpg.UndefinedTableError as e:
                    print(f"  ERROR (undefined table): {str(e)[:120]}")
                    errors += 1
                except Exception as e:
                    short = str(e).split("\n")[0][:120]
                    # Only print non-trivial errors
                    if "already exists" not in short.lower():
                        print(f"  WARN: {short}")
                    skipped += 1

            print(f"  OK={ok}  skipped={skipped}  errors={errors}\n")

        # ── Verify result ──────────────────────────────────────
        print("--- Verification ---")
        for tbl in ["agents", "memory_listings", "memory_chunks", "queries", "ratings",
                    "seller_reputation", "transaction_history", "disputes"]:
            exists = await table_exists(conn, tbl)
            print(f"  {'✓' if exists else '✗'} {tbl}")

    finally:
        await conn.close()

    print("\n=== Migration complete ===\n")


if __name__ == "__main__":
    asyncio.run(run())
