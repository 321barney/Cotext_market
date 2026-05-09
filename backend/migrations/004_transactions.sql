-- Migration 004: Transaction History and Dispute Resolution
-- PostgreSQL-compatible
-- Creates immutable transaction records and formal dispute tracking

-- ============================================
-- 1. Transaction History: immutable record of all marketplace activities
-- ============================================

CREATE TABLE transaction_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Participants
    buyer_agent_id UUID NOT NULL REFERENCES agents(id),
    seller_agent_id UUID NOT NULL REFERENCES agents(id),
    listing_id UUID NOT NULL REFERENCES memory_listings(id),
    query_id UUID REFERENCES queries(id),

    -- Transaction details
    type TEXT NOT NULL, -- 'query_payment', 'settlement', 'refund', 'dispute_opened', 'dispute_resolved', 'fee_collected', 'delivery'
    amount_usdc DECIMAL(12, 4) NOT NULL,
    fee_usdc DECIMAL(12, 4) DEFAULT 0, -- platform fee portion

    -- Status
    status TEXT NOT NULL DEFAULT 'pending', -- pending, completed, failed
    tx_hash TEXT, -- on-chain tx hash

    -- Metadata
    description TEXT,
    metadata JSONB DEFAULT '{}', -- flexible metadata (dispute reason, resolution, etc.)

    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_tx_history_buyer ON transaction_history(buyer_agent_id, created_at DESC);
CREATE INDEX idx_tx_history_seller ON transaction_history(seller_agent_id, created_at DESC);
CREATE INDEX idx_tx_history_listing ON transaction_history(listing_id, created_at DESC);
CREATE INDEX idx_tx_history_query ON transaction_history(query_id);
CREATE INDEX idx_tx_history_type ON transaction_history(type);
CREATE INDEX idx_tx_history_created ON transaction_history(created_at DESC);

-- ============================================
-- 2. Dispute Resolution: formal dispute tracking
-- ============================================

CREATE TABLE disputes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL UNIQUE REFERENCES queries(id),

    -- Participants
    buyer_agent_id UUID NOT NULL REFERENCES agents(id),
    seller_agent_id UUID NOT NULL REFERENCES agents(id),
    listing_id UUID NOT NULL REFERENCES memory_listings(id),

    -- Dispute details
    reason TEXT NOT NULL, -- buyer's stated reason
    evidence JSONB DEFAULT '{}', -- structured evidence (answer text, expected answer, etc.)

    -- Status
    status TEXT NOT NULL DEFAULT 'open', -- open, under_review, resolved_buyer, resolved_seller, canceled

    -- Resolution
    resolution TEXT, -- description of resolution
    refund_amount DECIMAL(12, 4) DEFAULT 0, -- amount refunded to buyer (0 = no refund)
    resolved_by UUID REFERENCES agents(id), -- who resolved (null = auto/system)

    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_disputes_buyer ON disputes(buyer_agent_id);
CREATE INDEX idx_disputes_seller ON disputes(seller_agent_id);
CREATE INDEX idx_disputes_status ON disputes(status);
CREATE INDEX idx_disputes_open ON disputes(status) WHERE status = 'open';
