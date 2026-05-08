"""
Reputation v2 — Composite scoring with 5 dimensions

Dimensions:
1. Buyer Ratings (40%) — rolling 30-day weighted average
2. Semantic Relevance (15%) — cosine sim between Q&A embeddings
3. Response Time (10%) — avg ms from payment to delivery
4. Fulfillment Rate (15%) — % queries successfully answered
5. Buyer Diversity (10%) — unique buyers / total queries
6. Dispute/Refund Penalty (10%) — inverse of dispute + refund rates

Composite Score (0-100) → Tier → Platform Fee
"""

import math
from app.database import db

# Tier thresholds and fee structure
TIERS = {
    "platinum": {"min_score": 80, "fee_bps": 700, "label": "💎 Platinum"},   # 7%
    "gold":     {"min_score": 60, "fee_bps": 800, "label": "🥇 Gold"},      # 8%
    "silver":   {"min_score": 40, "fee_bps": 900, "label": "🥈 Silver"},    # 9%
    "bronze":   {"min_score": 20, "fee_bps": 1000, "label": "🥉 Bronze"},   # 10%
    "unrated":  {"min_score": 0,  "fee_bps": 1000, "label": "— Unrated"},   # 10%
}

async def update_seller_reputation(seller_id: str):
    """
    Full reputation recalculation.
    Called after: new rating, query completion, dispute resolution.
    """
    # 1. Buyer Ratings (30-day weighted)
    ratings = await db.fetchrow(
        """
        SELECT 
            COUNT(*) as total_ratings,
            ROUND(AVG(score), 2) as avg_rating,
            ROUND(
                SUM(score * (1.0 / (1 + EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0))) 
                / NULLIF(SUM(1.0 / (1 + EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0)), 0)
            , 2) as weighted_score
        FROM ratings
        WHERE seller_agent_id = $1
          AND created_at > NOW() - INTERVAL '30 days'
        """,
        seller_id
    )
    
    total_ratings = ratings["total_ratings"] or 0
    avg_rating = ratings["avg_rating"] or 0
    weighted_score = ratings["weighted_score"] or 0
    
    # 2. Semantic Relevance (avg cosine similarity Q→A, last 30 days)
    semantic = await db.fetchrow(
        """
        SELECT 
            ROUND(AVG(semantic_relevance), 2) as avg_semantic,
            COUNT(*) as count
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE m.agent_id = $1
          AND q.semantic_relevance IS NOT NULL
          AND q.completed_at > NOW() - INTERVAL '30 days'
        """,
        seller_id
    )
    avg_semantic = semantic["avg_semantic"] or 0
    semantic_count = semantic["count"] or 0
    
    # 3. Response Time (avg ms, last 30 days)
    response_time = await db.fetchrow(
        """
        SELECT 
            ROUND(AVG(response_time_ms)) as avg_ms,
            COUNT(*) as count
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE m.agent_id = $1
          AND q.response_time_ms IS NOT NULL
          AND q.completed_at > NOW() - INTERVAL '30 days'
        """,
        seller_id
    )
    avg_response_ms = response_time["avg_ms"] or 0
    
    # 4. Fulfillment Rate (last 30 days)
    fulfillment = await db.fetchrow(
        """
        SELECT 
            COUNT(*) FILTER (WHERE status IN ('pending', 'completed', 'settled')) as fulfilled,
            COUNT(*) as total
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE m.agent_id = $1
          AND q.created_at > NOW() - INTERVAL '30 days'
        """,
        seller_id
    )
    fulfillment_rate = (fulfillment["fulfilled"] / fulfillment["total"] * 100) if fulfillment["total"] > 0 else 0
    
    # 5. Dispute & Refund Rates (last 30 days)
    disputes = await db.fetchrow(
        """
        SELECT 
            COUNT(*) FILTER (WHERE q.disputed = TRUE) as disputed_count,
            COUNT(*) FILTER (WHERE q.status = 'refunded') as refunded_count,
            COUNT(*) as total
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE m.agent_id = $1
          AND q.created_at > NOW() - INTERVAL '30 days'
        """,
        seller_id
    )
    dispute_rate = (disputes["disputed_count"] / disputes["total"] * 100) if disputes["total"] > 0 else 0
    refund_rate = (disputes["refunded_count"] / disputes["total"] * 100) if disputes["total"] > 0 else 0
    
    # 6. Buyer Diversity (unique buyers, last 30 days)
    diversity = await db.fetchrow(
        """
        SELECT 
            COUNT(DISTINCT buyer_agent_id) as unique_buyers,
            COUNT(*) as total_queries
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE m.agent_id = $1
          AND q.created_at > NOW() - INTERVAL '30 days'
        """,
        seller_id
    )
    unique_buyers = diversity["unique_buyers"] or 0
    total_queries = diversity["total_queries"] or 0
    diversity_ratio = (unique_buyers / total_queries * 100) if total_queries > 0 else 0
    
    # === COMPOSITE SCORE CALCULATION ===
    # Each dimension normalized to 0-100, then weighted
    
    # 1. Ratings score (0-100) — weighted_score is already 1-5, scale to 0-100
    rating_score = min((weighted_score / 5.0) * 100, 100) if weighted_score else 0
    
    # 2. Semantic relevance (0-100) — already 0-1, scale to 0-100
    semantic_score = min(avg_semantic * 100, 100) if avg_semantic else 0
    
    # 3. Response time (0-100) — faster is better
    # Target: <2s = 100, >30s = 0, linear between
    if avg_response_ms == 0:
        response_score = 50  # neutral if no data
    else:
        response_score = max(0, min(100, 100 - (avg_response_ms - 2000) / 280))
    
    # 4. Fulfillment rate (0-100) — already a percentage
    fulfillment_score = fulfillment_rate
    
    # 5. Buyer diversity (0-100) — ratio * 100, capped at 100
    diversity_score = min(diversity_ratio, 100)
    
    # 6. Dispute/Refund penalty (0-100) — start at 100, subtract penalties
    # Each 1% dispute = -5 points, each 1% refund = -3 points
    penalty_score = max(0, 100 - (dispute_rate * 5) - (refund_rate * 3))
    
    # Composite (weighted average)
    composite = (
        rating_score * 0.40 +
        semantic_score * 0.15 +
        response_score * 0.10 +
        fulfillment_score * 0.15 +
        diversity_score * 0.10 +
        penalty_score * 0.10
    )
    composite = round(composite, 2)
    
    # === TIER ASSIGNMENT ===
    # Need at least 10 ratings + 30-day activity to be rated
    if total_ratings < 10 or total_queries < 5:
        tier = "unrated"
    else:
        # Find highest tier the composite score qualifies for
        tier = "unrated"
        for t_name, t_data in sorted(TIERS.items(), key=lambda x: x[1]["min_score"], reverse=True):
            if composite >= t_data["min_score"]:
                tier = t_name
                break
    
    fee_bps = TIERS[tier]["fee_bps"]
    
    # === UPSERT ===
    await db.execute(
        """
        INSERT INTO seller_reputation (
            seller_agent_id, weighted_score, total_ratings, avg_rating,
            composite_score, tier, platform_fee_bps,
            fulfillment_rate, dispute_rate, refund_rate,
            unique_buyers, avg_response_time_ms, avg_semantic_relevance,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
        ON CONFLICT (seller_agent_id) DO UPDATE SET
            weighted_score = EXCLUDED.weighted_score,
            total_ratings = EXCLUDED.total_ratings,
            avg_rating = EXCLUDED.avg_rating,
            composite_score = EXCLUDED.composite_score,
            tier = EXCLUDED.tier,
            platform_fee_bps = EXCLUDED.platform_fee_bps,
            fulfillment_rate = EXCLUDED.fulfillment_rate,
            dispute_rate = EXCLUDED.dispute_rate,
            refund_rate = EXCLUDED.refund_rate,
            unique_buyers = EXCLUDED.unique_buyers,
            avg_response_time_ms = EXCLUDED.avg_response_time_ms,
            avg_semantic_relevance = EXCLUDED.avg_semantic_relevance,
            updated_at = NOW()
        """,
        seller_id,
        weighted_score or 0,
        total_ratings,
        avg_rating or 0,
        composite,
        tier,
        fee_bps,
        round(fulfillment_rate, 2),
        round(dispute_rate, 2),
        round(refund_rate, 2),
        unique_buyers,
        int(avg_response_ms) if avg_response_ms else None,
        avg_semantic if avg_semantic else None
    )
    
    return {
        "composite_score": composite,
        "tier": tier,
        "platform_fee_bps": fee_bps,
        "total_ratings": total_ratings,
        "weighted_score": weighted_score,
        "avg_rating": avg_rating,
        "fulfillment_rate": round(fulfillment_rate, 2),
        "dispute_rate": round(dispute_rate, 2),
        "refund_rate": round(refund_rate, 2),
        "unique_buyers": unique_buyers,
        "avg_response_time_ms": int(avg_response_ms) if avg_response_ms else None,
        "avg_semantic_relevance": avg_semantic,
    }

async def get_seller_reputation(agent_id: str) -> dict:
    """Get full reputation profile for a seller."""
    result = await db.fetchrow(
        """
        SELECT 
            weighted_score, total_ratings, avg_rating,
            composite_score, tier, platform_fee_bps,
            fulfillment_rate, dispute_rate, refund_rate,
            unique_buyers, avg_response_time_ms, avg_semantic_relevance
        FROM seller_reputation
        WHERE seller_agent_id = $1
        """,
        agent_id
    )
    
    if not result:
        return {
            "status": "unrated",
            "tier": "unrated",
            "composite_score": None,
            "total_ratings": 0,
        }
    
    tier_label = TIERS.get(result["tier"], TIERS["unrated"])["label"]
    
    return {
        "status": "active" if result["total_ratings"] >= 10 else "building",
        "tier": result["tier"],
        "tier_label": tier_label,
        "composite_score": float(result["composite_score"]) if result["composite_score"] else None,
        "weighted_score": float(result["weighted_score"]) if result["weighted_score"] else None,
        "total_ratings": result["total_ratings"],
        "avg_rating": float(result["avg_rating"]) if result["avg_rating"] else None,
        "platform_fee": f"{result['platform_fee_bps'] / 100:.1f}%",
        "platform_fee_bps": result["platform_fee_bps"],
        "fulfillment_rate": float(result["fulfillment_rate"]) if result["fulfillment_rate"] else None,
        "dispute_rate": float(result["dispute_rate"]) if result["dispute_rate"] else None,
        "refund_rate": float(result["refund_rate"]) if result["refund_rate"] else None,
        "unique_buyers": result["unique_buyers"],
        "avg_response_time_ms": result["avg_response_time_ms"],
        "avg_semantic_relevance": float(result["avg_semantic_relevance"]) if result["avg_semantic_relevance"] else None,
    }

async def get_seller_reputation_all_time(agent_id: str) -> dict:
    """Get all-time stats for dashboard."""
    result = await db.fetchrow(
        """
        SELECT 
            COUNT(*) as total_ratings,
            ROUND(AVG(score), 2) as average_score,
            ROUND(
                SUM(CASE WHEN score >= 4 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
            , 1) as positive_rate
        FROM ratings
        WHERE seller_agent_id = $1
        """,
        agent_id
    )
    
    if not result:
        return {"total_ratings": 0, "average_score": None, "positive_rate": None}
    
    return {
        "total_ratings": result["total_ratings"],
        "average_score": float(result["average_score"]) if result["average_score"] else None,
        "positive_rate": float(result["positive_rate"]) if result["positive_rate"] else None,
    }

async def get_tier_for_seller(seller_id: str) -> str:
    """Quick tier lookup (used for fee calculation during query)."""
    result = await db.fetchval(
        "SELECT tier FROM seller_reputation WHERE seller_agent_id = $1",
        seller_id
    )
    return result or "unrated"

async def get_platform_fee_for_seller(seller_id: str) -> int:
    """Get platform fee in basis points for a seller (used during settlement)."""
    result = await db.fetchval(
        "SELECT platform_fee_bps FROM seller_reputation WHERE seller_agent_id = $1",
        seller_id
    )
    return result or 1000  # default 10%

def calculate_tier_from_score(composite: float, total_ratings: int, total_queries: int) -> str:
    """Standalone tier calculator (for tests / verification)."""
    if total_ratings < 10 or total_queries < 5:
        return "unrated"
    
    for t_name, t_data in sorted(TIERS.items(), key=lambda x: x[1]["min_score"], reverse=True):
        if composite >= t_data["min_score"]:
            return t_name
    
    return "unrated"
