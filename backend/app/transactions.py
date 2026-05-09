"""
Transaction Workflow
Manages the complete lifecycle of a marketplace transaction:

States:
1. query_created     -- query record created, payment required
2. payment_verified  -- buyer deposited USDC to escrow
3. delivered         -- answer provided, in dispute window
4. settled           -- funds released to seller (after dispute window)
5. disputed          -- buyer opened dispute
6. refunded          -- funds returned to buyer
7. failed            -- permanent failure (no seller wallet, etc.)

Every state transition creates an immutable record in transaction_history.
"""

import uuid
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from fastapi import HTTPException

from app.database import db
from app.payments import refund_query

logger = logging.getLogger("transactions")


# ============================================
# Core: Record Immutable Transaction
# ============================================

async def record_transaction(
    buyer_agent_id: str,
    seller_agent_id: str,
    listing_id: str,
    query_id: str,
    tx_type: str,
    amount_usdc: Decimal,
    fee_usdc: Decimal = Decimal("0"),
    status: str = "completed",
    tx_hash: str = None,
    description: str = None,
    metadata: dict = None
) -> str:
    """
    Record an immutable transaction in transaction_history.
    This is the ONLY way to create transaction records -- they are append-only.

    Returns:
        str: The transaction record UUID
    """
    valid_types = {
        'query_payment', 'settlement', 'refund', 'dispute_opened',
        'dispute_resolved', 'fee_collected', 'delivery', 'failed'
    }
    if tx_type not in valid_types:
        raise ValueError(f"Invalid tx_type '{tx_type}'. Allowed: {valid_types}")

    metadata = metadata or {}

    row = await db.fetchrow(
        """
        INSERT INTO transaction_history (
            buyer_agent_id, seller_agent_id, listing_id, query_id,
            type, amount_usdc, fee_usdc, status, tx_hash,
            description, metadata, completed_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                CASE WHEN $8 = 'completed' THEN NOW() ELSE NULL END)
        RETURNING id
        """,
        buyer_agent_id, seller_agent_id, listing_id, query_id,
        tx_type, amount_usdc, fee_usdc, status, tx_hash,
        description, metadata
    )

    tx_id = str(row["id"])

    logger.info(
        f"TX_RECORDED | tx_id={tx_id} | type={tx_type} | "
        f"amount={amount_usdc} | buyer={buyer_agent_id} | seller={seller_agent_id} | "
        f"query={query_id} | status={status}"
    )

    return tx_id


# ============================================
# Query: Get Agent Transactions
# ============================================

async def get_agent_transactions(
    agent_id: str,
    role: str = "all",
    tx_type: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0
) -> dict:
    """
    Get paginated transaction history for an agent.

    Returns:
        {
            "transactions": [...],
            "total": int,
            "limit": int,
            "offset": int,
            "summary": {
                "total_spent": Decimal,
                "total_earned": Decimal,
                "total_fees": Decimal,
                "query_count": int,
                "dispute_count": int
            }
        }
    """
    # Build WHERE clause based on role filter
    if role == "buyer":
        role_filter = "buyer_agent_id = $1"
    elif role == "seller":
        role_filter = "seller_agent_id = $1"
    else:
        role_filter = "(buyer_agent_id = $1 OR seller_agent_id = $1)"

    # Base query parameters
    params = [agent_id]
    param_idx = 2

    # Type filter
    type_clause = ""
    if tx_type:
        type_clause = f"AND type = ${param_idx}"
        params.append(tx_type)
        param_idx += 1

    # Status filter
    status_clause = ""
    if status:
        status_clause = f"AND status = ${param_idx}"
        params.append(status)
        param_idx += 1

    # Count query
    count_sql = f"""
        SELECT COUNT(*) FROM transaction_history
        WHERE {role_filter}
        {type_clause}
        {status_clause}
    """
    total = await db.fetchval(count_sql, *params) or 0

    # Data query (add limit/offset params)
    data_params = list(params)
    data_sql = f"""
        SELECT
            id, type, amount_usdc, fee_usdc, status,
            buyer_agent_id, seller_agent_id, listing_id, query_id,
            tx_hash, description, metadata, created_at, completed_at
        FROM transaction_history
        WHERE {role_filter}
        {type_clause}
        {status_clause}
        ORDER BY created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """
    data_params.extend([limit, offset])

    rows = await db.fetch(data_sql, *data_params)

    transactions = []
    for r in rows:
        transactions.append({
            "id": str(r["id"]),
            "type": r["type"],
            "amount_usdc": r["amount_usdc"],
            "fee_usdc": r["fee_usdc"],
            "status": r["status"],
            "buyer_agent_id": str(r["buyer_agent_id"]),
            "seller_agent_id": str(r["seller_agent_id"]),
            "listing_id": str(r["listing_id"]),
            "query_id": str(r["query_id"]) if r["query_id"] else None,
            "tx_hash": r["tx_hash"],
            "description": r["description"],
            "metadata": r["metadata"] or {},
            "created_at": r["created_at"],
            "completed_at": r["completed_at"],
        })

    # Summary: spending as buyer
    summary_buyer = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(amount_usdc), 0) as total_spent,
            COALESCE(SUM(fee_usdc), 0) as total_fees,
            COUNT(*) FILTER (WHERE type = 'query_payment') as query_count,
            COUNT(*) FILTER (WHERE type = 'dispute_opened') as dispute_count
        FROM transaction_history
        WHERE buyer_agent_id = $1 AND status = 'completed'
        """,
        agent_id
    )

    # Summary: earnings as seller
    summary_seller = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(amount_usdc - fee_usdc), 0) as total_earned,
            COALESCE(SUM(fee_usdc), 0) as total_fees_paid
        FROM transaction_history
        WHERE seller_agent_id = $1 AND type = 'settlement' AND status = 'completed'
        """,
        agent_id
    )

    return {
        "transactions": transactions,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": {
            "total_spent": summary_buyer["total_spent"] or Decimal("0"),
            "total_earned": summary_seller["total_earned"] or Decimal("0"),
            "total_fees": (summary_buyer["total_fees"] or Decimal("0")) + (summary_seller["total_fees_paid"] or Decimal("0")),
            "query_count": summary_buyer["query_count"] or 0,
            "dispute_count": summary_buyer["dispute_count"] or 0,
        }
    }


# ============================================
# Dispute: Open Dispute
# ============================================

async def open_dispute(
    query_id: str,
    buyer_agent_id: str,
    reason: str,
    evidence: dict = None
) -> dict:
    """
    Buyer opens a dispute on a query within the dispute window.

    Steps:
        1. Verify buyer owns the query
        2. Verify query is in 'pending' status (dispute window still open)
        3. Mark query as 'disputed'
        4. Create dispute record
        5. Create transaction_history record
        6. Return dispute details

    Raises:
        HTTPException: 404 if query not found, 403 if not buyer's query,
                       400 if dispute window expired or already disputed
    """
    evidence = evidence or {}

    # 1. Verify query exists and buyer owns it
    query = await db.fetchrow(
        """
        SELECT q.id, q.status, q.release_at, q.buyer_agent_id,
               q.listing_id, q.cost, m.agent_id as seller_agent_id
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE q.id = $1
        """,
        query_id
    )

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    if str(query["buyer_agent_id"]) != str(buyer_agent_id):
        raise HTTPException(status_code=403, detail="Not your query")

    # 2. Verify query is in 'pending' status (delivered, within dispute window)
    if query["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Query not in disputable status. Current: {query['status']}"
        )

    # Check dispute window
    if query["release_at"] and query["release_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Dispute window expired")

    # 3. Check if dispute already exists
    existing = await db.fetchval(
        "SELECT id FROM disputes WHERE query_id = $1",
        query_id
    )
    if existing:
        raise HTTPException(status_code=409, detail="Dispute already exists for this query")

    # 4. Create dispute record
    dispute_row = await db.fetchrow(
        """
        INSERT INTO disputes (
            query_id, buyer_agent_id, seller_agent_id, listing_id,
            reason, evidence, status
        )
        VALUES ($1, $2, $3, $4, $5, $6, 'open')
        RETURNING id, created_at
        """,
        query_id, buyer_agent_id, query["seller_agent_id"], query["listing_id"],
        reason, evidence
    )

    # 5. Mark query as disputed
    await db.execute(
        """
        UPDATE queries
        SET status = 'disputed', disputed = TRUE
        WHERE id = $1
        """,
        query_id
    )

    # 6. Record transaction
    tx_id = await record_transaction(
        buyer_agent_id=buyer_agent_id,
        seller_agent_id=str(query["seller_agent_id"]),
        listing_id=str(query["listing_id"]),
        query_id=query_id,
        tx_type="dispute_opened",
        amount_usdc=query["cost"],
        description=f"Dispute opened: {reason[:200]}",
        metadata={"dispute_id": str(dispute_row["id"]), "reason": reason, "evidence": evidence}
    )

    logger.info(
        f"DISPUTE_OPENED | dispute_id={dispute_row['id']} | query_id={query_id} | "
        f"buyer={buyer_agent_id} | reason={reason[:100]}"
    )

    return {
        "dispute_id": str(dispute_row["id"]),
        "query_id": query_id,
        "status": "open",
        "reason": reason,
        "refund_amount": Decimal("0"),
        "created_at": dispute_row["created_at"],
        "resolved_at": None,
        "message": "Dispute filed. Settlement halted until resolution.",
    }


# ============================================
# Dispute: Resolve Dispute
# ============================================

async def resolve_dispute(
    dispute_id: str,
    resolution: str,
    refund_amount: Decimal = Decimal("0"),
    resolver_id: str = None,
    notes: str = None
) -> dict:
    """
    Resolve a dispute (platform admin or automated system).

    Steps:
        1. Update dispute record with resolution
        2. If refund: call payments.refund_query()
        3. If seller wins: query stays settled normally
        4. Create transaction_history record
        5. Update buyer and seller reputation
        6. Return resolution details

    Args:
        dispute_id: UUID of the dispute
        resolution: 'resolved_buyer', 'resolved_seller', or 'canceled'
        refund_amount: Amount to refund to buyer (if buyer wins)
        resolver_id: UUID of the agent resolving (null = system)
        notes: Optional resolution notes

    Raises:
        HTTPException: 404 if dispute not found, 400 if invalid resolution
    """
    valid_resolutions = {"resolved_buyer", "resolved_seller", "canceled"}
    if resolution not in valid_resolutions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resolution '{resolution}'. Allowed: {valid_resolutions}"
        )

    # 1. Get dispute details
    dispute = await db.fetchrow(
        """
        SELECT d.id, d.query_id, d.buyer_agent_id, d.seller_agent_id,
               d.listing_id, d.status, d.reason, q.cost, q.status as query_status,
               a.wallet_address as buyer_wallet
        FROM disputes d
        JOIN queries q ON q.id = d.query_id
        JOIN agents a ON a.id = d.buyer_agent_id
        WHERE d.id = $1
        """,
        dispute_id
    )

    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if dispute["status"] != "open":
        raise HTTPException(
            status_code=400,
            detail=f"Dispute already resolved with status: {dispute['status']}"
        )

    query_id = str(dispute["query_id"])
    buyer_id = str(dispute["buyer_agent_id"])
    seller_id = str(dispute["seller_agent_id"])
    listing_id = str(dispute["listing_id"])
    cost = dispute["cost"] or Decimal("0")
    buyer_wallet = dispute["buyer_wallet"]

    # 2. Handle resolution type
    tx_metadata = {
        "dispute_id": dispute_id,
        "resolution": resolution,
        "notes": notes,
        "refund_amount": str(refund_amount) if refund_amount else "0",
    }

    tx_hash = None
    refund_success = False

    if resolution == "resolved_buyer":
        # Buyer wins -- refund if wallet available
        if buyer_wallet and refund_amount > 0:
            refund_ok, result = await refund_query(query_id, buyer_wallet)
            if refund_ok:
                tx_hash = result
                refund_success = True
                await db.execute(
                    """
                    UPDATE queries
                    SET status = 'refunded', tx_hash = $1, settled_at = NOW()
                    WHERE id = $2
                    """,
                    tx_hash, query_id
                )
            else:
                logger.error(f"REFUND_FAILED | query={query_id} | error={result}")
                tx_metadata["refund_error"] = result

        elif not buyer_wallet:
            tx_metadata["refund_error"] = "Buyer has no wallet configured"

        # Update dispute record
        await db.execute(
            """
            UPDATE disputes
            SET status = 'resolved_buyer',
                resolution = $1,
                refund_amount = $2,
                resolved_by = $3,
                resolved_at = NOW()
            WHERE id = $4
            """,
            notes or "Buyer wins -- refund issued",
            refund_amount,
            resolver_id,
            dispute_id
        )

        # Record transaction
        await record_transaction(
            buyer_agent_id=buyer_id,
            seller_agent_id=seller_id,
            listing_id=listing_id,
            query_id=query_id,
            tx_type="dispute_resolved",
            amount_usdc=cost,
            description=f"Dispute resolved in buyer's favor. Refund: {refund_amount} USDC",
            metadata=tx_metadata,
            tx_hash=tx_hash
        )

    elif resolution == "resolved_seller":
        # Seller wins -- allow settlement to proceed
        await db.execute(
            """
            UPDATE disputes
            SET status = 'resolved_seller',
                resolution = $1,
                refund_amount = 0,
                resolved_by = $2,
                resolved_at = NOW()
            WHERE id = $3
            """,
            notes or "Seller wins -- funds released",
            resolver_id,
            dispute_id
        )

        # Release query for settlement (scheduler will pick it up)
        await db.execute(
            """
            UPDATE queries
            SET status = 'pending', disputed = FALSE
            WHERE id = $1
            """,
            query_id
        )

        # Record transaction
        await record_transaction(
            buyer_agent_id=buyer_id,
            seller_agent_id=seller_id,
            listing_id=listing_id,
            query_id=query_id,
            tx_type="dispute_resolved",
            amount_usdc=cost,
            description="Dispute resolved in seller's favor. Funds released for settlement.",
            metadata=tx_metadata
        )

    elif resolution == "canceled":
        # Dispute canceled (e.g., buyer withdrew)
        await db.execute(
            """
            UPDATE disputes
            SET status = 'canceled',
                resolution = $1,
                refund_amount = 0,
                resolved_by = $2,
                resolved_at = NOW()
            WHERE id = $3
            """,
            notes or "Dispute canceled",
            resolver_id,
            dispute_id
        )

        # Restore query to pending for settlement
        await db.execute(
            """
            UPDATE queries
            SET status = 'pending', disputed = FALSE
            WHERE id = $1
            """,
            query_id
        )

        # Record transaction
        await record_transaction(
            buyer_agent_id=buyer_id,
            seller_agent_id=seller_id,
            listing_id=listing_id,
            query_id=query_id,
            tx_type="dispute_resolved",
            amount_usdc=Decimal("0"),
            description="Dispute canceled. Query returned to pending settlement.",
            metadata=tx_metadata
        )

    # 5. Update reputation for both parties
    try:
        from app.reputation import update_seller_reputation
        await update_seller_reputation(seller_id)
    except Exception as e:
        logger.warning(f"Reputation update failed for seller {seller_id}: {e}")

    logger.info(
        f"DISPUTE_RESOLVED | dispute_id={dispute_id} | resolution={resolution} | "
        f"refund={refund_amount} | resolver={resolver_id or 'system'}"
    )

    return {
        "dispute_id": dispute_id,
        "query_id": query_id,
        "status": resolution,
        "resolution": notes,
        "refund_amount": refund_amount,
        "refund_issued": refund_success,
        "tx_hash": tx_hash,
        "resolved_by": resolver_id,
        "resolved_at": datetime.utcnow(),
    }


# ============================================
# Dashboard: Transaction Summary
# ============================================

async def get_transaction_summary(agent_id: str) -> dict:
    """
    Get comprehensive financial summary for an agent (as both buyer and seller).

    Returns:
        {
            "as_buyer": {
                "total_queries": int,
                "total_spent": Decimal,
                "total_disputes": int,
                "avg_cost_per_query": Decimal
            },
            "as_seller": {
                "total_queries_served": int,
                "total_earned": Decimal,
                "total_fees_paid": Decimal,
                "avg_earnings_per_query": Decimal,
                "dispute_rate": float
            },
            "this_month": {
                "spent": Decimal,
                "earned": Decimal,
                "fees": Decimal,
                "queries": int,
                "disputes": int
            }
        }
    """
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # --- As Buyer ---
    buyer_stats = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(amount_usdc), 0) as total_spent,
            COUNT(*) FILTER (WHERE type = 'query_payment') as total_queries,
            COUNT(*) FILTER (WHERE type = 'dispute_opened') as total_disputes,
            COALESCE(AVG(amount_usdc) FILTER (WHERE type = 'query_payment'), 0) as avg_cost
        FROM transaction_history
        WHERE buyer_agent_id = $1 AND status = 'completed'
        """,
        agent_id
    )

    # --- As Seller ---
    seller_stats = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(amount_usdc - fee_usdc), 0) as total_earned,
            COALESCE(SUM(fee_usdc), 0) as total_fees_paid,
            COUNT(*) FILTER (WHERE type = 'settlement') as total_settlements,
            COALESCE(AVG(amount_usdc - fee_usdc) FILTER (WHERE type = 'settlement'), 0) as avg_earnings
        FROM transaction_history
        WHERE seller_agent_id = $1 AND status = 'completed'
        """,
        agent_id
    )

    # Total queries served (count distinct queries settled)
    queries_served = await db.fetchval(
        """
        SELECT COUNT(DISTINCT query_id)
        FROM transaction_history
        WHERE seller_agent_id = $1 AND type = 'settlement' AND status = 'completed'
        """,
        agent_id
    ) or 0

    # Dispute rate: disputes / settlements * 100
    dispute_count = seller_stats["total_settlements"] or 0
    total_settled = queries_served
    dispute_rate = round((dispute_count / max(total_settled, 1)) * 100, 2)

    # --- This Month ---
    month_stats = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(amount_usdc) FILTER (WHERE buyer_agent_id = $1), 0) as spent,
            COALESCE(SUM(amount_usdc - fee_usdc) FILTER (WHERE seller_agent_id = $1 AND type = 'settlement'), 0) as earned,
            COALESCE(SUM(fee_usdc) FILTER (WHERE buyer_agent_id = $1 OR seller_agent_id = $1), 0) as fees,
            COUNT(*) FILTER (WHERE buyer_agent_id = $1 AND type = 'query_payment') as queries,
            COUNT(*) FILTER (WHERE buyer_agent_id = $1 AND type = 'dispute_opened') as disputes
        FROM transaction_history
        WHERE (buyer_agent_id = $1 OR seller_agent_id = $1)
          AND created_at >= $2
          AND status = 'completed'
        """,
        agent_id, month_start
    )

    return {
        "as_buyer": {
            "total_queries": buyer_stats["total_queries"] or 0,
            "total_spent": buyer_stats["total_spent"] or Decimal("0"),
            "total_disputes": buyer_stats["total_disputes"] or 0,
            "avg_cost_per_query": round(buyer_stats["avg_cost"] or Decimal("0"), 4),
        },
        "as_seller": {
            "total_queries_served": queries_served,
            "total_earned": seller_stats["total_earned"] or Decimal("0"),
            "total_fees_paid": seller_stats["total_fees_paid"] or Decimal("0"),
            "avg_earnings_per_query": round(seller_stats["avg_earnings"] or Decimal("0"), 4),
            "dispute_rate": dispute_rate,
        },
        "this_month": {
            "spent": month_stats["spent"] or Decimal("0"),
            "earned": month_stats["earned"] or Decimal("0"),
            "fees": month_stats["fees"] or Decimal("0"),
            "queries": month_stats["queries"] or 0,
            "disputes": month_stats["disputes"] or 0,
        }
    }


# ============================================
# Dispute: Get by Query ID
# ============================================

async def get_dispute_by_query(query_id: str, agent_id: str = None) -> Optional[dict]:
    """
    Get dispute record for a query.
    If agent_id is provided, verifies the agent is buyer or seller.

    Returns None if no dispute exists.
    """
    row = await db.fetchrow(
        """
        SELECT d.id, d.query_id, d.buyer_agent_id, d.seller_agent_id,
               d.reason, d.evidence, d.status, d.resolution,
               d.refund_amount, d.resolved_by, d.created_at, d.resolved_at
        FROM disputes d
        WHERE d.query_id = $1
        """,
        query_id
    )

    if not row:
        return None

    # Auth check
    if agent_id:
        if str(row["buyer_agent_id"]) != str(agent_id) and str(row["seller_agent_id"]) != str(agent_id):
            raise HTTPException(status_code=403, detail="Not authorized to view this dispute")

    return {
        "dispute_id": str(row["id"]),
        "query_id": str(row["query_id"]),
        "status": row["status"],
        "reason": row["reason"],
        "evidence": row["evidence"] or {},
        "resolution": row["resolution"],
        "refund_amount": row["refund_amount"] or Decimal("0"),
        "resolved_by": str(row["resolved_by"]) if row["resolved_by"] else None,
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
    }


# ============================================
# Settlement: Record settlement transaction
# ============================================

async def record_settlement_transaction(
    query_id: str,
    amount_usdc: Decimal,
    fee_usdc: Decimal,
    tx_hash: str
) -> str:
    """
    Convenience wrapper to record a settlement transaction.
    Looks up buyer, seller, and listing from the query record.
    """
    query = await db.fetchrow(
        """
        SELECT q.buyer_agent_id, q.listing_id, q.cost, m.agent_id as seller_agent_id
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE q.id = $1
        """,
        query_id
    )

    if not query:
        logger.error(f"Cannot record settlement: query {query_id} not found")
        return None

    return await record_transaction(
        buyer_agent_id=str(query["buyer_agent_id"]),
        seller_agent_id=str(query["seller_agent_id"]),
        listing_id=str(query["listing_id"]),
        query_id=query_id,
        tx_type="settlement",
        amount_usdc=amount_usdc,
        fee_usdc=fee_usdc,
        status="completed",
        tx_hash=tx_hash,
        description=f"Settlement: {amount_usdc - fee_usdc} to seller, {fee_usdc} fee"
    )


# ============================================
# Delivery: Record delivery transaction
# ============================================

async def record_delivery_transaction(
    query_id: str,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    cost: Decimal
) -> str:
    """
    Convenience wrapper to record a delivery transaction.
    Called when an answer is delivered to the buyer.
    """
    return await record_transaction(
        buyer_agent_id=buyer_id,
        seller_agent_id=seller_id,
        listing_id=listing_id,
        query_id=query_id,
        tx_type="delivery",
        amount_usdc=cost,
        status="completed",
        description="Answer delivered, dispute window open"
    )


# ============================================
# Payment: Record payment transaction
# ============================================

async def record_payment_transaction(
    query_id: str,
    buyer_id: str,
    seller_id: str,
    listing_id: str,
    cost: Decimal
) -> str:
    """
    Convenience wrapper to record a payment verification transaction.
    Called when buyer's escrow deposit is confirmed.
    """
    return await record_transaction(
        buyer_agent_id=buyer_id,
        seller_agent_id=seller_id,
        listing_id=listing_id,
        query_id=query_id,
        tx_type="query_payment",
        amount_usdc=cost,
        status="completed",
        description="Payment verified in escrow"
    )
