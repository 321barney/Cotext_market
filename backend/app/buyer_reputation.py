"""
Buyer Reputation System
Tracks buyer behavior to protect sellers from abuse.

Dimensions:
1. Activity (20%) -- query volume, purchase amount, seller diversity
2. Rating Quality (30%) -- does buyer rate fairly (avg around 3)?
3. Dispute/Refund Rate (30%) -- lower is better
4. Rating Consistency (20%) -- std dev of ratings (lower = more consistent)

Composite Score (0-100) -> Tier
- vip: 80+ (excellent buyer, reduced fees for sellers)
- trusted: 60+ (good buyer)
- standard: 40+ (normal buyer)
- flagged: <40 (high dispute/refund rate, sellers warned)
"""

import math
from app.database import db

# Tier thresholds for buyers
BUYER_TIERS = {
    "vip":      {"min_score": 80, "label": "VIP"},
    "trusted":  {"min_score": 60, "label": "Trusted"},
    "standard": {"min_score": 40, "label": "Standard"},
    "flagged":  {"min_score": 0,  "label": "Flagged"},
}


async def update_buyer_reputation(buyer_id: str) -> dict:
    """
    Full buyer reputation recalculation.

    Called after: new rating, query completion, dispute resolution, refund.

    Calculates a composite score (0-100) from four dimensions:
        - Activity (20%): query volume and purchase diversity
        - Rating Quality (30%): whether buyer rates fairly (centered at 3.0)
        - Penalty (30%): dispute and refund rate penalties
        - Consistency (20%): standard deviation of ratings given

    Args:
        buyer_id: The UUID of the buyer agent to recalculate.

    Returns:
        dict with composite score, tier, and all component metrics.
    """

    # --- 1. Activity Metrics (last 30 days) ---
    activity = await db.fetchrow(
        """
        SELECT
            COUNT(*) as total_queries,
            COALESCE(SUM(cost), 0) as total_purchases,
            COUNT(DISTINCT m.agent_id) as unique_sellers
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE q.buyer_agent_id = $1
          AND q.created_at > NOW() - INTERVAL '30 days'
        """,
        buyer_id
    )
    total_queries = activity["total_queries"] or 0
    total_purchases = activity["total_purchases"] or 0
    unique_sellers = activity["unique_sellers"] or 0

    # --- 2. Rating Quality (ratings buyer has given, last 30 days) ---
    rating_stats = await db.fetchrow(
        """
        SELECT
            COUNT(*) as ratings_given,
            ROUND(AVG(score), 2) as avg_rating_given,
            COALESCE(STDDEV(score), 0) as rating_stddev
        FROM ratings
        WHERE buyer_agent_id = $1
          AND created_at > NOW() - INTERVAL '30 days'
        """,
        buyer_id
    )
    ratings_given = rating_stats["ratings_given"] or 0
    avg_rating_given = rating_stats["avg_rating_given"] or 0
    rating_stddev = rating_stats["rating_stddev"] or 0

    # --- 3. Dispute & Refund Rates (last 30 days) ---
    disputes = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE disputed = TRUE) as disputed_count,
            COUNT(*) FILTER (WHERE status = 'refunded') as refunded_count,
            COUNT(*) as total
        FROM queries
        WHERE buyer_agent_id = $1
          AND created_at > NOW() - INTERVAL '30 days'
        """,
        buyer_id
    )
    dispute_rate = (disputes["disputed_count"] / disputes["total"] * 100) if disputes["total"] > 0 else 0
    refund_rate = (disputes["refunded_count"] / disputes["total"] * 100) if disputes["total"] > 0 else 0

    # --- 4. Fulfillment Rate (% queries NOT disputed/refunded) ---
    fulfillment_rate = 100.0 - dispute_rate - refund_rate

    # === COMPOSITE SCORE CALCULATION ===

    # 1. Activity score (0-100)
    #   Scale: 50 queries = full 100 points
    activity_score = min((total_queries / 50) * 100, 100) if total_queries > 0 else 0

    # 2. Rating Quality score (0-100)
    #   Centered at 3.0 (fair). 1.0 or 5.0 = 0 points. 3.0 = 100 points.
    if ratings_given > 0 and avg_rating_given > 0:
        rating_quality_score = max(0, (1 - abs(avg_rating_given - 3.0) / 2.0) * 100)
    else:
        rating_quality_score = 50  # neutral if no ratings given yet

    # 3. Penalty score (0-100)
    #   Each 1% dispute = -10 points, each 1% refund = -5 points
    penalty_score = max(0, 100 - (dispute_rate * 10) - (refund_rate * 5))

    # 4. Consistency score (0-100)
    #   Lower stddev = more consistent. 0 stddev = 100 points. 4+ stddev = 0 points.
    if ratings_given >= 2:
        consistency_score = max(0, 100 - rating_stddev * 25)
    else:
        consistency_score = 50  # neutral if not enough ratings

    # Weighted composite (0-100)
    composite = (
        activity_score * 0.20 +
        rating_quality_score * 0.30 +
        penalty_score * 0.30 +
        consistency_score * 0.20
    )
    composite = round(composite, 2)

    # === TIER ASSIGNMENT ===
    tier = _tier_from_score(composite)

    # === UPSERT ===
    await db.execute(
        """
        INSERT INTO buyer_reputation (
            buyer_agent_id, total_queries, total_purchases, unique_sellers,
            avg_rating_given, ratings_given, dispute_rate, refund_rate,
            composite_score, tier, fulfillment_rate, rating_stddev,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
        ON CONFLICT (buyer_agent_id) DO UPDATE SET
            total_queries = EXCLUDED.total_queries,
            total_purchases = EXCLUDED.total_purchases,
            unique_sellers = EXCLUDED.unique_sellers,
            avg_rating_given = EXCLUDED.avg_rating_given,
            ratings_given = EXCLUDED.ratings_given,
            dispute_rate = EXCLUDED.dispute_rate,
            refund_rate = EXCLUDED.refund_rate,
            composite_score = EXCLUDED.composite_score,
            tier = EXCLUDED.tier,
            fulfillment_rate = EXCLUDED.fulfillment_rate,
            rating_stddev = EXCLUDED.rating_stddev,
            updated_at = NOW()
        """,
        buyer_id,
        total_queries,
        total_purchases,
        unique_sellers,
        round(avg_rating_given, 2) if avg_rating_given else None,
        ratings_given,
        round(dispute_rate, 2),
        round(refund_rate, 2),
        composite,
        tier,
        round(fulfillment_rate, 2),
        round(rating_stddev, 2) if rating_stddev else None
    )

    return {
        "buyer_agent_id": buyer_id,
        "composite_score": composite,
        "tier": tier,
        "total_queries": total_queries,
        "total_purchases": float(total_purchases),
        "unique_sellers": unique_sellers,
        "avg_rating_given": round(avg_rating_given, 2) if avg_rating_given else None,
        "ratings_given": ratings_given,
        "dispute_rate": round(dispute_rate, 2),
        "refund_rate": round(refund_rate, 2),
        "fulfillment_rate": round(fulfillment_rate, 2),
        "rating_stddev": round(rating_stddev, 2) if rating_stddev else None,
        "component_scores": {
            "activity": round(activity_score, 2),
            "rating_quality": round(rating_quality_score, 2),
            "penalty": round(penalty_score, 2),
            "consistency": round(consistency_score, 2),
        }
    }


async def get_buyer_reputation(agent_id: str) -> dict:
    """
    Get full buyer reputation profile.

    Args:
        agent_id: The UUID of the buyer agent.

    Returns:
        dict with reputation data, or a default 'unknown' profile if not found.
    """
    result = await db.fetchrow(
        """
        SELECT
            buyer_agent_id, total_queries, total_purchases, unique_sellers,
            avg_rating_given, ratings_given, dispute_rate, refund_rate,
            composite_score, tier, fulfillment_rate, rating_stddev, updated_at
        FROM buyer_reputation
        WHERE buyer_agent_id = $1
        """,
        agent_id
    )

    if not result:
        return {
            "status": "unknown",
            "tier": "standard",
            "composite_score": None,
            "total_queries": 0,
            "total_purchases": 0,
            "unique_sellers": 0,
            "avg_rating_given": None,
            "ratings_given": 0,
            "dispute_rate": 0.0,
            "refund_rate": 0.0,
            "fulfillment_rate": 100.0,
        }

    tier_label = BUYER_TIERS.get(result["tier"], BUYER_TIERS["standard"])["label"]

    return {
        "buyer_agent_id": str(result["buyer_agent_id"]),
        "status": "active" if result["total_queries"] >= 1 else "building",
        "tier": result["tier"],
        "tier_label": tier_label,
        "composite_score": float(result["composite_score"]) if result["composite_score"] else None,
        "total_queries": result["total_queries"],
        "total_purchases": float(result["total_purchases"]) if result["total_purchases"] else 0,
        "unique_sellers": result["unique_sellers"],
        "avg_rating_given": float(result["avg_rating_given"]) if result["avg_rating_given"] else None,
        "ratings_given": result["ratings_given"],
        "dispute_rate": float(result["dispute_rate"]) if result["dispute_rate"] else 0.0,
        "refund_rate": float(result["refund_rate"]) if result["refund_rate"] else 0.0,
        "fulfillment_rate": float(result["fulfillment_rate"]) if result["fulfillment_rate"] else 100.0,
        "rating_stddev": float(result["rating_stddev"]) if result["rating_stddev"] else None,
        "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None,
    }


async def get_buyer_tier(buyer_id: str) -> str:
    """
    Quick tier lookup for a buyer (used for fee calculations, warnings).

    Args:
        buyer_id: The UUID of the buyer agent.

    Returns:
        str tier name: 'vip', 'trusted', 'standard', or 'flagged'.
        Defaults to 'standard' if no reputation record exists.
    """
    result = await db.fetchval(
        "SELECT tier FROM buyer_reputation WHERE buyer_agent_id = $1",
        buyer_id
    )
    return result or "standard"


async def is_buyer_flagged(buyer_id: str) -> bool:
    """
    Check if a buyer is flagged (high dispute/refund rate).

    Args:
        buyer_id: The UUID of the buyer agent.

    Returns:
        True if the buyer is flagged, False otherwise.
    """
    result = await db.fetchval(
        "SELECT tier FROM buyer_reputation WHERE buyer_agent_id = $1",
        buyer_id
    )
    return result == "flagged"


def _tier_from_score(composite: float) -> str:
    """
    Assign tier based on composite score.

    Args:
        composite: Composite score (0-100).

    Returns:
        str tier name: 'vip', 'trusted', 'standard', or 'flagged'.
    """
    if composite >= 80:
        return "vip"
    elif composite >= 60:
        return "trusted"
    elif composite >= 40:
        return "standard"
    else:
        return "flagged"


def calculate_buyer_tier_from_score(composite: float) -> str:
    """
    Standalone tier calculator (for tests / verification).

    Args:
        composite: Composite score (0-100).

    Returns:
        str tier name: 'vip', 'trusted', 'standard', or 'flagged'.
    """
    return _tier_from_score(composite)
