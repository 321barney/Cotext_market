-- Migration 003: Buyer Reputation & Context Quality Scoring

-- ============================================================
-- 1. Buyer Reputation
--    Tracks buyer behavior to protect sellers from abuse.
-- ============================================================

CREATE TABLE IF NOT EXISTS buyer_reputation (
    buyer_agent_id UUID PRIMARY KEY REFERENCES agents(id),

    -- Activity metrics
    total_queries INTEGER DEFAULT 0,
    total_purchases DECIMAL(12, 4) DEFAULT 0.00, -- total USDC spent
    unique_sellers INTEGER DEFAULT 0,

    -- Quality metrics
    avg_rating_given DECIMAL(3, 2), -- average rating the buyer gives (detects harsh/lenient raters)
    ratings_given INTEGER DEFAULT 0,

    -- Trust metrics
    dispute_rate DECIMAL(5, 2) DEFAULT 0.00, -- % queries disputed
    refund_rate DECIMAL(5, 2) DEFAULT 0.00, -- % queries refunded

    -- Composite score
    composite_score DECIMAL(5, 2) DEFAULT 50.00, -- starts neutral at 50
    tier TEXT DEFAULT 'standard', -- standard, trusted, vip, flagged

    -- Computed fields
    fulfillment_rate DECIMAL(5, 2) DEFAULT 100.00, -- % queries NOT disputed/refunded
    rating_stddev DECIMAL(5, 2), -- std dev of ratings (consistency measure)

    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_buyer_reputation_score ON buyer_reputation(composite_score DESC);
CREATE INDEX IF NOT EXISTS idx_buyer_reputation_tier ON buyer_reputation(tier);

-- ============================================================
-- 2. Context Quality
--    Per-listing quality score based on multi-dimensional metrics.
-- ============================================================

CREATE TABLE IF NOT EXISTS context_quality (
    listing_id UUID PRIMARY KEY REFERENCES memory_listings(id) ON DELETE CASCADE,

    -- Quality dimensions
    avg_semantic_relevance DECIMAL(3, 2), -- avg Q-A cosine similarity
    avg_rating DECIMAL(3, 2), -- avg buyer rating
    avg_response_time_ms INTEGER, -- avg delivery speed
    total_ratings INTEGER DEFAULT 0,

    -- Composite quality score (0-100)
    quality_score DECIMAL(5, 2) DEFAULT 50.00,
    quality_tier TEXT DEFAULT 'unrated', -- poor(0-40), fair(40-60), good(60-75), excellent(75-90), premium(90-100)

    -- Trust signals
    fulfillment_rate DECIMAL(5, 2) DEFAULT 100.00, -- % successfully answered
    buyer_diversity INTEGER DEFAULT 0, -- unique buyers

    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_context_quality_score ON context_quality(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_context_quality_tier ON context_quality(quality_tier);
