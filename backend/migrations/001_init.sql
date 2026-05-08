-- Context Market Database Schema
-- PostgreSQL + pgvector

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Agents (sellers and buyers)
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    did TEXT UNIQUE, -- optional decentralized identifier
    api_key_hash TEXT UNIQUE NOT NULL, -- sha256 of api key
    wallet_address TEXT, -- EVM wallet for x402 payments
    wallet_chain TEXT DEFAULT 'base', -- chain for x402
    credit_balance DECIMAL(12, 2) DEFAULT 0.00, -- deprecated, kept for compatibility
    earnings_balance DECIMAL(12, 2) DEFAULT 0.00, -- seller earnings in USDC
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_api_key ON agents(api_key_hash);

-- 2. Memory Listings (what sellers publish)
CREATE TABLE memory_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL, -- e.g. 'trading', 'legal', 'coding'
    price_per_query DECIMAL(12, 4) NOT NULL, -- e.g. 0.1000 = $0.10
    query_limit_per_day INTEGER DEFAULT 100, -- max queries this listing accepts per day
    is_active BOOLEAN DEFAULT TRUE,
    total_queries INTEGER DEFAULT 0,
    total_earnings DECIMAL(12, 2) DEFAULT 0.00,
    raw_knowledge_text TEXT, -- full original text for dispute resolution
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_listings_agent ON memory_listings(agent_id);
CREATE INDEX idx_listings_category ON memory_listings(category);
CREATE INDEX idx_listings_active ON memory_listings(is_active) WHERE is_active = TRUE;

-- 3. Memory Chunks (pgvector-stored pieces)
CREATE TABLE memory_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES memory_listings(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL, -- the actual text snippet
    embedding VECTOR(384), -- all-MiniLM-L6-v2 = 384 dims
    chunk_index INTEGER NOT NULL, -- ordering within the listing
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- pgvector index for fast similarity search
CREATE INDEX idx_chunks_embedding ON memory_chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_chunks_listing ON memory_chunks(listing_id);

-- 4. Queries (every query with cost + response tracking)
CREATE TABLE queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_agent_id UUID NOT NULL REFERENCES agents(id),
    listing_id UUID NOT NULL REFERENCES memory_listings(id),
    question TEXT NOT NULL,
    question_embedding VECTOR(384), -- for fingerprinting
    answer TEXT,
    answer_embedding VECTOR(384), -- for semantic relevance scoring
    cost DECIMAL(12, 4) NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, completed, failed, insufficient_credits, payment_required, settled, refunded, disputed
    response_id UUID, -- links to ratings
    created_at TIMESTAMPTZ DEFAULT NOW(),
    payment_verified_at TIMESTAMPTZ, -- when escrow deposit was confirmed
    completed_at TIMESTAMPTZ,
    release_at TIMESTAMPTZ, -- when funds can be settled (24h dispute window)
    disputed BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER, -- milliseconds from payment verified to answer delivered
    semantic_relevance DECIMAL(3, 2), -- cosine similarity between question and answer embeddings
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX idx_queries_buyer_listing ON queries(buyer_agent_id, listing_id);
CREATE INDEX idx_queries_created ON queries(created_at);
CREATE INDEX idx_queries_buyer_created ON queries(buyer_agent_id, created_at);

-- 5. Transactions (credit ledger)
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    type TEXT NOT NULL, -- credit_purchase, query_spend, query_earn, payout
    amount DECIMAL(12, 4) NOT NULL, -- positive = credit added, negative = spent
    description TEXT,
    tx_hash TEXT, -- on-chain transaction hash for x402 payments
    related_query_id UUID REFERENCES queries(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transactions_agent ON transactions(agent_id);
CREATE INDEX idx_transactions_type ON transactions(type);

-- 6. Ratings (buyer scores on responses)
CREATE TABLE ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL UNIQUE REFERENCES queries(id),
    buyer_agent_id UUID NOT NULL REFERENCES agents(id),
    seller_agent_id UUID NOT NULL REFERENCES agents(id),
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ratings_seller ON ratings(seller_agent_id);
CREATE INDEX idx_ratings_created ON ratings(created_at);

-- 7. Seller Reputation (materialized as table for upserts)
CREATE TABLE seller_reputation (
    seller_agent_id UUID PRIMARY KEY REFERENCES agents(id),
    weighted_score DECIMAL(4, 2) DEFAULT 0.00, -- rolling 30-day weighted avg
    total_ratings INTEGER DEFAULT 0,
    avg_rating DECIMAL(3, 2) DEFAULT 0.00,
    -- Reputation Criteria v2
    composite_score DECIMAL(5, 2) DEFAULT 0.00, -- 0-100 composite
    tier TEXT DEFAULT 'unrated', -- unrated, bronze, silver, gold, platinum
    platform_fee_bps INTEGER DEFAULT 1000, -- 10% = 1000 bps
    fulfillment_rate DECIMAL(5, 2) DEFAULT 0.00, -- % queries successfully answered
    dispute_rate DECIMAL(5, 2) DEFAULT 0.00, -- % queries disputed
    refund_rate DECIMAL(5, 2) DEFAULT 0.00, -- % queries refunded
    unique_buyers INTEGER DEFAULT 0, -- distinct buyer count
    avg_response_time_ms INTEGER, -- average response time
    avg_semantic_relevance DECIMAL(3, 2), -- average semantic relevance
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reputation_score ON seller_reputation(weighted_score DESC);

-- Trigger: auto-update seller_reputation when a new rating is inserted
CREATE OR REPLACE FUNCTION refresh_seller_reputation()
RETURNS TRIGGER AS $$
BEGIN
    -- Basic weighted score update (composite + tier calculated by Python backend)
    INSERT INTO seller_reputation (seller_agent_id, weighted_score, total_ratings, avg_rating, updated_at)
    SELECT 
        NEW.seller_agent_id,
        ROUND(
            SUM(score * (1.0 / (1 + EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0))) 
            / NULLIF(SUM(1.0 / (1 + EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0)), 0)
        , 2),
        COUNT(*),
        ROUND(AVG(score), 2),
        NOW()
    FROM ratings
    WHERE seller_agent_id = NEW.seller_agent_id
      AND created_at > NOW() - INTERVAL '30 days'
    ON CONFLICT (seller_agent_id) DO UPDATE SET
        weighted_score = EXCLUDED.weighted_score,
        total_ratings = EXCLUDED.total_ratings,
        avg_rating = EXCLUDED.avg_rating,
        updated_at = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_refresh_reputation
AFTER INSERT ON ratings
FOR EACH ROW
EXECUTE FUNCTION refresh_seller_reputation();

-- Trigger: update agent earnings when query completes
CREATE OR REPLACE FUNCTION credit_seller_on_query()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        -- Add to seller earnings
        UPDATE agents 
        SET earnings_balance = earnings_balance + NEW.cost,
            updated_at = NOW()
        WHERE id = (SELECT agent_id FROM memory_listings WHERE id = NEW.listing_id);
        
        -- Update listing stats
        UPDATE memory_listings
        SET total_queries = total_queries + 1,
            total_earnings = total_earnings + NEW.cost,
            updated_at = NOW()
        WHERE id = NEW.listing_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_credit_seller
AFTER UPDATE ON queries
FOR EACH ROW
EXECUTE FUNCTION credit_seller_on_query();
