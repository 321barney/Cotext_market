"""
Context Quality Scoring
Evaluates the quality of knowledge listings based on five dimensions:

1. Semantic Relevance (30%) -- Q-A cosine similarity
2. Buyer Ratings (30%) -- average rating score
3. Response Time (15%) -- delivery speed
4. Fulfillment Rate (15%) -- % successfully answered
5. Buyer Diversity (10%) -- unique buyer count

Quality Tiers:
- premium:   90-100 (top listings, featured in search)
- excellent: 75-90
- good:      60-75
- fair:      40-60
- poor:      0-40  (demoted in search, flagged for review)
- unrated:   no data yet
"""

from app.database import db

# Quality tier thresholds
QUALITY_TIERS = {
    "premium":   {"min_score": 90, "label": "Premium"},
    "excellent": {"min_score": 75, "label": "Excellent"},
    "good":      {"min_score": 60, "label": "Good"},
    "fair":      {"min_score": 40, "label": "Fair"},
    "poor":      {"min_score": 0,  "label": "Poor"},
    "unrated":   {"min_score": 0,  "label": "Unrated"},
}


async def update_context_quality(listing_id: str) -> dict:
    """
    Full context quality recalculation for a listing.

    Called after: query completion, new rating, dispute resolution.

    Calculates a quality score (0-100) from five dimensions:
        - Semantic Relevance (30%): avg cosine similarity between Q&A embeddings
        - Buyer Ratings (30%): average buyer rating (1-5 scale)
        - Response Time (15%): delivery speed
        - Fulfillment Rate (15%): % queries successfully answered
        - Buyer Diversity (10%): unique buyer count

    Args:
        listing_id: The UUID of the memory listing to recalculate.

    Returns:
        dict with quality score, tier, and all component metrics.
    """

    # --- 1. Semantic Relevance (avg cosine similarity, last 30 days) ---
    semantic = await db.fetchrow(
        """
        SELECT
            ROUND(AVG(semantic_relevance), 2) as avg_semantic,
            COUNT(*) as count
        FROM queries
        WHERE listing_id = $1
          AND semantic_relevance IS NOT NULL
          AND completed_at > NOW() - INTERVAL '30 days'
        """,
        listing_id
    )
    avg_semantic = semantic["avg_semantic"] or 0
    semantic_count = semantic["count"] or 0

    # --- 2. Buyer Ratings (avg rating, last 30 days) ---
    ratings = await db.fetchrow(
        """
        SELECT
            COUNT(*) as total_ratings,
            ROUND(AVG(r.score), 2) as avg_rating
        FROM ratings r
        JOIN queries q ON q.id = r.query_id
        WHERE q.listing_id = $1
          AND r.created_at > NOW() - INTERVAL '30 days'
        """,
        listing_id
    )
    total_ratings = ratings["total_ratings"] or 0
    avg_rating = ratings["avg_rating"] or 0

    # --- 3. Response Time (avg ms, last 30 days) ---
    response_time = await db.fetchrow(
        """
        SELECT
            ROUND(AVG(response_time_ms)) as avg_ms,
            COUNT(*) as count
        FROM queries
        WHERE listing_id = $1
          AND response_time_ms IS NOT NULL
          AND completed_at > NOW() - INTERVAL '30 days'
        """,
        listing_id
    )
    avg_response_ms = response_time["avg_ms"] or 0

    # --- 4. Fulfillment Rate (last 30 days) ---
    fulfillment = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status IN ('pending', 'completed', 'settled')) as fulfilled,
            COUNT(*) as total
        FROM queries
        WHERE listing_id = $1
          AND created_at > NOW() - INTERVAL '30 days'
        """,
        listing_id
    )
    fulfillment_rate = (fulfillment["fulfilled"] / fulfillment["total"] * 100) if fulfillment["total"] > 0 else 100.0

    # --- 5. Buyer Diversity (unique buyers, last 30 days) ---
    diversity = await db.fetchrow(
        """
        SELECT
            COUNT(DISTINCT buyer_agent_id) as unique_buyers,
            COUNT(*) as total_queries
        FROM queries
        WHERE listing_id = $1
          AND created_at > NOW() - INTERVAL '30 days'
        """,
        listing_id
    )
    unique_buyers = diversity["unique_buyers"] or 0
    total_queries = diversity["total_queries"] or 0

    # === COMPOSITE QUALITY SCORE CALCULATION ===

    # 1. Semantic score (0-1 -> 0-100)
    if avg_semantic > 0:
        semantic_score = min(avg_semantic * 100, 100)
    else:
        semantic_score = 50  # neutral if no data

    # 2. Rating score (1-5 scale -> 0-100)
    if avg_rating > 0:
        rating_score = min((avg_rating / 5.0) * 100, 100)
    else:
        rating_score = 50  # neutral if no ratings

    # 3. Response time score (0-100)
    #   Target: <2s = 100 points, >30s = 0 points, linear between
    if avg_response_ms > 0:
        response_score = max(0, min(100, 100 - (avg_response_ms - 2000) / 280))
    else:
        response_score = 50  # neutral if no data

    # 4. Fulfillment score (already 0-100)
    fulfillment_score = fulfillment_rate

    # 5. Diversity score (0-100)
    #   Scale: 20 unique buyers = full 100 points
    diversity_score = min((unique_buyers / 20) * 100, 100) if unique_buyers > 0 else 0

    # Weighted composite (0-100)
    quality_score = (
        semantic_score * 0.30 +
        rating_score * 0.30 +
        response_score * 0.15 +
        fulfillment_score * 0.15 +
        diversity_score * 0.10
    )
    quality_score = round(quality_score, 2)

    # === TIER ASSIGNMENT ===
    # Need at least 5 ratings + 5 queries to be rated
    if total_ratings < 5 or total_queries < 5:
        tier = "unrated"
    else:
        tier = _quality_tier_from_score(quality_score)

    # === UPSERT ===
    await db.execute(
        """
        INSERT INTO context_quality (
            listing_id, avg_semantic_relevance, avg_rating,
            avg_response_time_ms, total_ratings, quality_score,
            quality_tier, fulfillment_rate, buyer_diversity,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        ON CONFLICT (listing_id) DO UPDATE SET
            avg_semantic_relevance = EXCLUDED.avg_semantic_relevance,
            avg_rating = EXCLUDED.avg_rating,
            avg_response_time_ms = EXCLUDED.avg_response_time_ms,
            total_ratings = EXCLUDED.total_ratings,
            quality_score = EXCLUDED.quality_score,
            quality_tier = EXCLUDED.quality_tier,
            fulfillment_rate = EXCLUDED.fulfillment_rate,
            buyer_diversity = EXCLUDED.buyer_diversity,
            updated_at = NOW()
        """,
        listing_id,
        round(avg_semantic, 2) if avg_semantic else None,
        round(avg_rating, 2) if avg_rating else None,
        int(avg_response_ms) if avg_response_ms else None,
        total_ratings,
        quality_score,
        tier,
        round(fulfillment_rate, 2),
        unique_buyers
    )

    return {
        "listing_id": listing_id,
        "quality_score": quality_score,
        "quality_tier": tier,
        "avg_semantic_relevance": round(avg_semantic, 2) if avg_semantic else None,
        "avg_rating": round(avg_rating, 2) if avg_rating else None,
        "avg_response_time_ms": int(avg_response_ms) if avg_response_ms else None,
        "total_ratings": total_ratings,
        "fulfillment_rate": round(fulfillment_rate, 2),
        "buyer_diversity": unique_buyers,
        "component_scores": {
            "semantic": round(semantic_score, 2),
            "rating": round(rating_score, 2),
            "response": round(response_score, 2),
            "fulfillment": round(fulfillment_score, 2),
            "diversity": round(diversity_score, 2),
        }
    }


async def get_context_quality(listing_id: str) -> dict:
    """
    Get full quality profile for a listing.

    Args:
        listing_id: The UUID of the memory listing.

    Returns:
        dict with quality data, or a default 'unrated' profile if not found.
    """
    result = await db.fetchrow(
        """
        SELECT
            listing_id, quality_score, quality_tier,
            avg_semantic_relevance, avg_rating, avg_response_time_ms,
            total_ratings, fulfillment_rate, buyer_diversity, updated_at
        FROM context_quality
        WHERE listing_id = $1
        """,
        listing_id
    )

    if not result:
        return {
            "status": "unknown",
            "quality_tier": "unrated",
            "quality_score": None,
            "avg_semantic_relevance": None,
            "avg_rating": None,
            "avg_response_time_ms": None,
            "total_ratings": 0,
            "fulfillment_rate": 100.0,
            "buyer_diversity": 0,
        }

    tier_label = QUALITY_TIERS.get(result["quality_tier"], QUALITY_TIERS["unrated"])["label"]

    return {
        "listing_id": str(result["listing_id"]),
        "status": "rated" if result["total_ratings"] >= 5 else "building",
        "quality_tier": result["quality_tier"],
        "tier_label": tier_label,
        "quality_score": float(result["quality_score"]) if result["quality_score"] else None,
        "avg_semantic_relevance": float(result["avg_semantic_relevance"]) if result["avg_semantic_relevance"] else None,
        "avg_rating": float(result["avg_rating"]) if result["avg_rating"] else None,
        "avg_response_time_ms": result["avg_response_time_ms"],
        "total_ratings": result["total_ratings"],
        "fulfillment_rate": float(result["fulfillment_rate"]) if result["fulfillment_rate"] else 100.0,
        "buyer_diversity": result["buyer_diversity"],
        "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None,
    }


async def get_listings_by_quality(min_score: float = 0, tier: str = None):
    """
    Filter and list memory listings by quality criteria.

    Args:
        min_score: Minimum quality score (0-100). Default 0.
        tier: Filter by specific quality tier ('premium', 'excellent',
              'good', 'fair', 'poor', or 'unrated'). Default None (all tiers).

    Returns:
        list of dicts with listing quality data.
    """
    conditions = ["cq.quality_score >= $1"]
    params = [min_score]

    if tier:
        conditions.append(f"cq.quality_tier = ${len(params) + 1}")
        params.append(tier.lower())

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            cq.listing_id, cq.quality_score, cq.quality_tier,
            cq.avg_semantic_relevance, cq.avg_rating,
            cq.avg_response_time_ms, cq.total_ratings,
            cq.fulfillment_rate, cq.buyer_diversity,
            m.title, m.category, m.agent_id, a.name as agent_name,
            cq.updated_at
        FROM context_quality cq
        JOIN memory_listings m ON m.id = cq.listing_id
        JOIN agents a ON a.id = m.agent_id
        WHERE {where_clause}
        ORDER BY cq.quality_score DESC
    """

    rows = await db.fetch(query, *params)

    results = []
    for r in rows:
        results.append({
            "listing_id": str(r["listing_id"]),
            "title": r["title"],
            "category": r["category"],
            "agent_id": str(r["agent_id"]),
            "agent_name": r["agent_name"],
            "quality_score": float(r["quality_score"]) if r["quality_score"] else None,
            "quality_tier": r["quality_tier"],
            "avg_semantic_relevance": float(r["avg_semantic_relevance"]) if r["avg_semantic_relevance"] else None,
            "avg_rating": float(r["avg_rating"]) if r["avg_rating"] else None,
            "avg_response_time_ms": r["avg_response_time_ms"],
            "total_ratings": r["total_ratings"],
            "fulfillment_rate": float(r["fulfillment_rate"]) if r["fulfillment_rate"] else 100.0,
            "buyer_diversity": r["buyer_diversity"],
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        })

    return results


def _quality_tier_from_score(quality_score: float) -> str:
    """
    Assign quality tier based on score.

    Args:
        quality_score: Composite quality score (0-100).

    Returns:
        str tier name: 'premium', 'excellent', 'good', 'fair', or 'poor'.
    """
    if quality_score >= 90:
        return "premium"
    elif quality_score >= 75:
        return "excellent"
    elif quality_score >= 60:
        return "good"
    elif quality_score >= 40:
        return "fair"
    else:
        return "poor"


def calculate_quality_tier_from_score(quality_score: float) -> str:
    """
    Standalone quality tier calculator (for tests / verification).

    Args:
        quality_score: Composite quality score (0-100).

    Returns:
        str tier name: 'premium', 'excellent', 'good', 'fair', or 'poor'.
    """
    return _quality_tier_from_score(quality_score)
