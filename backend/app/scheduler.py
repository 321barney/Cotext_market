"""
Context Market — Settlement Scheduler
Runs every hour: settles queries that passed 24h release window.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from app.database import db
from app.payments import settle_query, retry_failed_settlement, refund_query

# Logging
log_base = os.getenv("LOG_DIR", "/root/.openclaw/workspace/innovations/context-market-v2/logs")
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

async def run_settlement_job():
    """
    Main settlement job.
    Finds queries ready for settlement (release_at < now) and settles them.
    """
    logger.info("=" * 60)
    logger.info("SETTLEMENT JOB STARTED")
    logger.info("=" * 60)
    
    # 1. Find queries ready for settlement
    # release_at has passed, status is 'pending', not disputed
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
        return
    
    logger.info(f"Found {len(queries)} queries to settle")
    
    settled_count = 0
    failed_count = 0
    
    for query in queries:
        query_id = str(query["id"])
        cost = query["cost"]
        
        logger.info(f"Settling query {query_id} (${cost} USDC)...")
        
        # Get seller wallet
        listing = await db.fetchrow(
            "SELECT agent_id FROM memory_listings WHERE id = $1",
            query["listing_id"]
        )
        
        if not listing:
            logger.error(f"Query {query_id}: Listing not found")
            failed_count += 1
            continue
        
        seller = await db.fetchrow(
            "SELECT wallet_address FROM agents WHERE id = $1",
            listing["agent_id"]
        )
        
        if not seller or not seller["wallet_address"]:
            logger.error(f"Query {query_id}: Seller has no wallet")
            failed_count += 1
            continue
        
        seller_wallet = seller["wallet_address"]
        
        # Attempt settlement
        success, result = await settle_query(query_id, seller_wallet, cost)
        
        if success:
            logger.info(f"Query {query_id}: SETTLED ✓ tx={result}")
            settled_count += 1
        else:
            logger.error(f"Query {query_id}: FAILED ✗ {result}")
            # Trigger retry logic
            retry_success, retry_msg = await retry_failed_settlement(query_id)
            logger.info(f"Query {query_id}: RETRY → {retry_msg}")
            failed_count += 1
    
    logger.info("=" * 60)
    logger.info(f"SETTLED: {settled_count} | FAILED: {failed_count}")
    logger.info("=" * 60)

async def run_dispute_resolution():
    """
    Process disputed queries.
    If dispute resolved as 'refund' → call refund().
    If 'release' → proceed with settlement.
    """
    logger.info("Checking disputed queries...")
    
    # Find disputed queries with resolution
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
        return
    
    for dispute in disputes:
        query_id = str(dispute["id"])
        resolution = dispute["resolution"]
        buyer_wallet = dispute["buyer_wallet"]
        
        if resolution == "refund":
            logger.info(f"Query {query_id}: Processing REFUND")
            success, result = await refund_query(query_id, buyer_wallet)
            if success:
                logger.info(f"Query {query_id}: REFUNDED ✓ tx={result}")
            else:
                logger.error(f"Query {query_id}: REFUND FAILED ✗ {result}")
                
        elif resolution == "release":
            logger.info(f"Query {query_id}: Processing RELEASE (settle)")
            # Mark as pending to be picked up by settlement job
            await db.execute(
                "UPDATE queries SET status = 'pending', disputed = false WHERE id = $1",
                query_id
            )
            logger.info(f"Query {query_id}: Released for settlement")

async def run_scheduler_loop():
    """Main scheduler loop — runs every hour."""
    logger.info("Settlement scheduler started. Running every hour.")
    
    while True:
        try:
            await run_settlement_job()
            await run_dispute_resolution()
        except Exception as e:
            logger.exception(f"Scheduler error: {e}")
        
        # Sleep 1 hour
        logger.info("Sleeping 1 hour...")
        await asyncio.sleep(3600)

def run_once():
    """Run settlement job once (for cron or manual execution)."""
    asyncio.run(run_settlement_job())

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        asyncio.run(run_scheduler_loop())
    else:
        run_once()
