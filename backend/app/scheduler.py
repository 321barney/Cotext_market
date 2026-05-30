"""
Context Market -- Settlement Scheduler
Runs every hour: settles queries that passed 24h release window.

Changes:
  * DB health-check before each run
  * Consecutive-failure detection with fatal-exit
  * SIGTERM / SIGINT graceful shutdown
  * Transient vs permanent error classification in settlement
  * Per-run metrics logging
  * Inserts permanent failures into failed_settlements table
"""

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from app.database import db
from app.payments import settle_query, retry_failed_settlement, refund_query

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_base = os.getenv("LOG_DIR", "/var/log/context-market")
log_dir = Path(log_base) / "settlements"
log_dir.mkdir(parents=True, exist_ok=True)

date_str = datetime.utcnow().strftime("%Y-%m-%d")
log_file = log_dir / f"{date_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler")

# ---------------------------------------------------------------------------
# Health / shutdown / failure counters
# ---------------------------------------------------------------------------
_shutdown_requested = False
_consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 5

# Error type classification for transient vs permanent failures
_TRANSIENT_ERRORS = (
    "network",
    "rpc",
    "timeout",
    "connection",
    "temporary",
    "nonce",
    "insufficient funds",
    "rate limit",
    "503",
    "504",
    "429",
    "EOF",
)

_PERMANENT_ERRORS = (
    "no wallet",
    "not found",
    "invalid",
    "blacklisted",
    "rejected",
    "permanent",
)


def _handle_signal(signum, frame):
    global _shutdown_requested
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    _shutdown_requested = True


# Register signal handlers (sync -- safe to do at import time)
signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


async def _health_check() -> bool:
    """Check if database is reachable."""
    try:
        return await db.health_check()
    except Exception:
        return False


def _classify_error(error_msg: str) -> str:
    """Classify an error message as 'transient' or 'permanent'."""
    err_lower = str(error_msg).lower()
    if any(kw in err_lower for kw in _PERMANENT_ERRORS):
        return "permanent"
    if any(kw in err_lower for kw in _TRANSIENT_ERRORS):
        return "transient"
    return "transient"  # Default to retry on unknown errors


async def _record_failed_settlement(query_id: str, error: str, error_type: str):
    """Insert a record into failed_settlements so we don't retry infinitely."""
    try:
        await db.execute(
            """
            INSERT INTO failed_settlements (query_id, error, error_type, created_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (query_id) DO UPDATE
                SET error = EXCLUDED.error,
                    error_type = EXCLUDED.error_type,
                    retry_count = failed_settlements.retry_count + 1,
                    last_retry_at = NOW()
            """,
            query_id, error, error_type
        )
        logger.info(f"Query {query_id}: Recorded in failed_settlements ({error_type})")
    except Exception as e:
        logger.error(f"Query {query_id}: Could not record failure: {e}")


# ---------------------------------------------------------------------------
# Settlement job
# ---------------------------------------------------------------------------
async def run_settlement_job():
    """
    Main settlement job.
    Finds queries ready for settlement (release_at < now) and settles them.
    """
    logger.info("=" * 60)
    logger.info("SETTLEMENT JOB STARTED")
    logger.info("=" * 60)

    # 1. Find queries ready for settlement
    queries = await db.fetch(
        """
        SELECT q.id, q.buyer_agent_id, q.listing_id, q.cost, q.release_at,
               a.wallet_address as buyer_wallet
        FROM queries q
        JOIN agents a ON a.id = q.buyer_agent_id
        WHERE q.status = 'pending'
          AND q.release_at IS NOT NULL
          AND q.release_at <= NOW()
          AND (q.disputed IS NULL OR q.disputed = false)
        ORDER BY q.release_at ASC
        LIMIT 100
        """
    )

    if not queries:
        logger.info("No queries ready for settlement")
        return 0, 0  # settled, failed

    logger.info(f"Found {len(queries)} queries to settle")

    settled_count = 0
    failed_count = 0

    for query in queries:
        # Check for graceful shutdown every iteration
        if _shutdown_requested:
            logger.info("Shutdown requested, stopping settlement mid-batch.")
            break

        query_id = str(query["id"])
        cost = query["cost"]

        logger.info(f"Settling query {query_id} (${cost} USDC)...")

        # -- Permanent: listing missing -----------------------------------
        listing = await db.fetchrow(
            "SELECT agent_id FROM memory_listings WHERE id = $1",
            query["listing_id"]
        )
        if not listing:
            err = "Listing not found"
            logger.error(f"Query {query_id}: {err}")
            await _record_failed_settlement(query_id, err, "permanent")
            failed_count += 1
            continue

        # -- Permanent: seller has no wallet ------------------------------
        seller = await db.fetchrow(
            "SELECT wallet_address FROM agents WHERE id = $1",
            listing["agent_id"]
        )
        if not seller or not seller["wallet_address"]:
            err = "Seller has no wallet"
            logger.error(f"Query {query_id}: {err}")
            await _record_failed_settlement(query_id, err, "permanent")
            failed_count += 1
            continue

        seller_wallet = seller["wallet_address"]

        # -- Attempt on-chain settlement ----------------------------------
        success, result = await settle_query(query_id, seller_wallet, cost)

        if success:
            logger.info(f"Query {query_id}: SETTLED ✓ tx={result}")
            settled_count += 1
        else:
            err_type = _classify_error(str(result))
            logger.error(f"Query {query_id}: FAILED ({err_type}) ✗ {result}")

            if err_type == "permanent":
                await _record_failed_settlement(query_id, str(result), "permanent")
            else:
                # Transient -- schedule retry via existing retry mechanism
                try:
                    retry_success, retry_msg = await retry_failed_settlement(query_id)
                    logger.info(f"Query {query_id}: RETRY → {retry_msg}")
                except Exception as re:
                    logger.error(f"Query {query_id}: Retry mechanism failed: {re}")

            failed_count += 1

    return settled_count, failed_count


# ---------------------------------------------------------------------------
# Dispute resolution
# ---------------------------------------------------------------------------
async def run_dispute_resolution():
    """
    Process disputed queries.
    If dispute resolved as 'refund' --> call refund().
    If 'release' --> proceed with settlement.
    """
    logger.info("Checking disputed queries...")

    disputes = await db.fetch(
        """
        SELECT q.id, q.buyer_agent_id, q.cost, d.resolution, a.wallet_address as buyer_wallet
        FROM queries q
        JOIN disputes d ON d.query_id = q.id
        JOIN agents a ON a.id = q.buyer_agent_id
        WHERE q.status = 'disputed'
          AND d.resolution IS NOT NULL
          AND d.resolved_at IS NOT NULL
        ORDER BY d.resolved_at ASC
        LIMIT 50
        """
    )

    if not disputes:
        logger.info("No resolved disputes to process")
        return 0  # disputes processed count

    processed = 0

    for dispute in disputes:
        if _shutdown_requested:
            logger.info("Shutdown requested, stopping dispute resolution mid-batch.")
            break

        query_id = str(dispute["id"])
        resolution = dispute["resolution"]
        buyer_wallet = dispute["buyer_wallet"]

        if resolution == "refund":
            logger.info(f"Query {query_id}: Processing REFUND")
            success, result = await refund_query(query_id, buyer_wallet)
            if success:
                logger.info(f"Query {query_id}: REFUNDED ✓ tx={result}")
            else:
                err_type = _classify_error(str(result))
                logger.error(f"Query {query_id}: REFUND FAILED ({err_type}) ✗ {result}")
                await _record_failed_settlement(query_id, f"refund: {result}", err_type)

        elif resolution == "release":
            logger.info(f"Query {query_id}: Processing RELEASE (settle)")
            await db.execute(
                "UPDATE queries SET status = 'pending', disputed = false WHERE id = $1",
                query_id
            )
            logger.info(f"Query {query_id}: Released for settlement")

        processed += 1

    return processed


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
async def run_scheduler_loop():
    """Main scheduler loop -- runs every hour."""
    global _consecutive_failures

    logger.info("Settlement scheduler started. Running every hour.")

    while True:
        # -- Graceful shutdown check -------------------------------------
        if _shutdown_requested:
            logger.info("Shutdown complete. Exiting scheduler loop.")
            break

        run_ok = False
        run_start = time.time()
        metrics = {"settled": 0, "failed": 0, "disputes": 0}

        try:
            # -- DB health check -----------------------------------------
            db_healthy = await _health_check()
            if not db_healthy:
                logger.error("DB health check FAILED -- skipping this cycle")
            else:
                # -- Settlement job --------------------------------------
                metrics["settled"], metrics["failed"] = await run_settlement_job()

                # -- Dispute resolution ----------------------------------
                metrics["disputes"] = await run_dispute_resolution()

                run_ok = True

        except Exception as e:
            logger.exception(f"Scheduler error: {e}")

        # -- Update failure counter & fatal check ------------------------
        elapsed = time.time() - run_start

        if run_ok:
            _consecutive_failures = 0
        else:
            _consecutive_failures += 1
            logger.warning(
                f"Run failed (consecutive failures: {_consecutive_failures})"
            )
            if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    f"Too many consecutive failures ({_consecutive_failures}). "
                    "Exiting so systemd can restart."
                )
                sys.exit(1)

        # -- Metrics logging ---------------------------------------------
        logger.info("=" * 60)
        logger.info(
            f"METRICS  settled={metrics['settled']}  "
            f"failed={metrics['failed']}  "
            f"disputes={metrics['disputes']}  "
            f"elapsed={elapsed:.2f}s"
        )
        logger.info("=" * 60)

        # -- Sleep with shutdown awareness --------------------------------
        logger.info("Sleeping 1 hour...")
        for _ in range(360):
            if _shutdown_requested:
                break
            await asyncio.sleep(10)  # Wake every 10s to check _shutdown_requested

        if _shutdown_requested:
            logger.info("Shutdown complete. Exiting scheduler loop.")
            break


def run_once():
    """Run settlement job once (for cron or manual execution)."""
    asyncio.run(_run_once_impl())


async def _run_once_impl():
    """Async implementation of single-run execution."""
    db_healthy = await _health_check()
    if not db_healthy:
        logger.error("DB health check FAILED -- aborting single run")
        return

    run_start = time.time()
    settled, failed = await run_settlement_job()
    disputes = await run_dispute_resolution()
    elapsed = time.time() - run_start

    logger.info("=" * 60)
    logger.info(
        f"METRICS  settled={settled}  "
        f"failed={failed}  "
        f"disputes={disputes}  "
        f"elapsed={elapsed:.2f}s"
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        asyncio.run(run_scheduler_loop())
    else:
        run_once()
