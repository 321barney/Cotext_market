from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# ======================
# Capability Taxonomy (hard-coded reference list)
# ======================

CAPABILITY_TAXONOMY: List[str] = [
    "text-generation",
    "code-generation",
    "image-generation",
    "audio-generation",
    "video-generation",
    "data-analysis",
    "web-search",
    "document-parsing",
    "translation",
    "summarization",
    "classification",
    "embedding",
    "retrieval",
    "tool-use",
    "memory",
    "planning",
    "multi-agent",
    "staking",
    "trading",
    "legal",
    "medical",
    "customer-support",
    "education",
    "research",
]

# Trusted agent types that go through verification challenge
TRUSTED_AGENT_TYPES: set = {"langchain", "crewai", "autogen"}
# Simple agent types that auto-verify
AUTO_VERIFY_TYPES: set = {"custom", "unknown"}

# ======================
# Request Schemas
# ======================

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    wallet_address: Optional[str] = None
    wallet_chain: str = "base"
    agent_type: str = Field(default="unknown", max_length=50)
    agent_capabilities: List[str] = Field(default_factory=list)
    agent_version: Optional[str] = Field(None, max_length=50)
    agent_endpoint: Optional[str] = Field(None, max_length=500)

    @field_validator("agent_endpoint")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_stripped = v.strip()
        if not v_stripped:
            return None
        if not (v_stripped.startswith("http://") or v_stripped.startswith("https://")):
            raise ValueError("agent_endpoint must be a valid HTTP/HTTPS URL")
        return v_stripped

    @field_validator("agent_capabilities")
    @classmethod
    def validate_capabilities(cls, v: List[str]) -> List[str]:
        validated = []
        for cap in v:
            cap_clean = cap.strip().lower()
            if cap_clean:
                validated.append(cap_clean)
        return validated


class AgentVerifyRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    verification_method: str = Field(default="manual", max_length=50)


class MemoryStoreRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    knowledge_text: str = Field(..., min_length=10)
    price_per_query: Decimal = Field(..., ge=0.01)
    query_limit_per_day: int = Field(default=100, ge=1)


class MemoryQueryRequest(BaseModel):
    listing_id: str
    question: str = Field(..., min_length=1, max_length=1000)


class RateQueryRequest(BaseModel):
    query_id: str
    score: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class CreditPurchaseRequest(BaseModel):
    amount_cents: int = Field(..., ge=100, le=1000000)


# ======================
# Response Schemas
# ======================

class AgentRegisterResponse(BaseModel):
    agent_id: str
    name: str
    api_key: str
    created_at: datetime
    agent_type: str = "unknown"
    agent_capabilities: List[str] = []
    verified_agent: bool = False
    verification_method: Optional[str] = None


class AgentVerifyResponse(BaseModel):
    agent_id: str
    verified: bool
    verification_method: str
    verified_at: datetime


class AgentInfoResponse(BaseModel):
    agent_id: str
    name: str
    agent_type: str
    agent_capabilities: List[str]
    agent_version: Optional[str]
    agent_endpoint: Optional[str]
    verified_agent: bool
    verification_method: Optional[str]
    created_at: datetime


class MemoryListingResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    title: str
    description: Optional[str]
    category: Optional[str]
    price_per_query: Decimal
    total_queries: int
    reputation_score: Optional[Decimal]
    created_at: datetime


class MemoryQueryResponse(BaseModel):
    query_id: str
    answer: str
    cost: Decimal
    confidence: float
    seller_id: str
    seller_name: str
    created_at: datetime


class AgentEarningsResponse(BaseModel):
    agent_id: str
    name: str
    credit_balance: Decimal
    earnings_balance: Decimal
    total_queries_served: int
    total_earnings: Decimal


class AgentReputationResponse(BaseModel):
    agent_id: str
    name: str
    reputation_score: Optional[float]
    total_ratings: int
    is_rated: bool


class CapabilityTaxonomyItem(BaseModel):
    name: str
    display_name: str
    description: Optional[str]


class CapabilityListResponse(BaseModel):
    capabilities: List[CapabilityTaxonomyItem]


# ======================
# Discovery Response Models
# ======================

class DiscoveryAgentItem(BaseModel):
    """A single discovered agent listing with combined listing + agent info."""
    listing_id: str
    title: str
    description: Optional[str]
    category: Optional[str]
    price_per_query: Decimal
    total_queries: int
    created_at: datetime
    agent_id: str
    agent_name: str
    agent_type: str
    agent_capabilities: List[str] = []
    agent_version: Optional[str] = None
    verified_agent: bool = False
    reputation_score: Optional[float] = None
    tier: Optional[str] = None


class AgentDiscoveryResponse(BaseModel):
    """Response for /agents/discover semantic search endpoint."""
    agents: List[DiscoveryAgentItem]
    total: int
    limit: int
    offset: int


# ======================
# Manifest Response Models
# ======================

class ManifestInfo(BaseModel):
    title: str
    version: str
    description: str


class ManifestPayment(BaseModel):
    protocol: str
    chain: str
    chain_id: int
    token: str
    token_contract: str


class ManifestVerification(BaseModel):
    required: bool
    methods: List[str]


class AgentManifestResponse(BaseModel):
    openapi: str
    info: ManifestInfo
    capabilities: dict
    payment: ManifestPayment
    agent_types: List[str]
    verification: ManifestVerification


class ErrorResponse(BaseModel):
    error: str
    code: str
    detail: Optional[str] = None


# ======================
# Transaction Models
# ======================

class TransactionItem(BaseModel):
    id: str
    type: str
    amount_usdc: Decimal
    fee_usdc: Decimal
    status: str
    buyer_agent_id: str
    seller_agent_id: str
    listing_id: str
    query_id: Optional[str] = None
    tx_hash: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class TransactionListResponse(BaseModel):
    transactions: List[TransactionItem]
    total: int
    limit: int
    offset: int
    summary: dict


class TransactionSummary(BaseModel):
    as_buyer: dict
    as_seller: dict
    this_month: dict


# ======================
# Dispute Models
# ======================

class DisputeRequest(BaseModel):
    query_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=10, max_length=1000)
    evidence: Optional[dict] = None


class DisputeResponse(BaseModel):
    dispute_id: str
    query_id: str
    status: str
    reason: str
    refund_amount: Decimal
    created_at: datetime
    resolved_at: Optional[datetime] = None


class DisputeResolutionRequest(BaseModel):
    dispute_id: str
    resolution: str = Field(..., pattern="^(resolved_buyer|resolved_seller|canceled)$")
    refund_amount: Decimal = Decimal("0")
    notes: Optional[str] = None


# ======================
# Buyer Reputation Models
# ======================

class BuyerReputationResponse(BaseModel):
    """Full buyer reputation profile response."""
    buyer_agent_id: str
    total_queries: int
    total_purchases: Decimal
    unique_sellers: int
    avg_rating_given: Optional[float]
    ratings_given: int
    dispute_rate: float
    refund_rate: float
    composite_score: float
    tier: str
    fulfillment_rate: float


class BuyerReputationDetailResponse(BaseModel):
    """Extended buyer reputation with component score breakdown."""
    buyer_agent_id: str
    status: str
    tier: str
    tier_label: str
    composite_score: Optional[float]
    total_queries: int
    total_purchases: float
    unique_sellers: int
    avg_rating_given: Optional[float]
    ratings_given: int
    dispute_rate: float
    refund_rate: float
    fulfillment_rate: float
    rating_stddev: Optional[float]
    updated_at: Optional[str] = None


# ======================
# Context Quality Models
# ======================

class ContextQualityResponse(BaseModel):
    """Full context quality profile for a listing."""
    listing_id: str
    quality_score: float
    quality_tier: str
    avg_semantic_relevance: Optional[float]
    avg_rating: Optional[float]
    avg_response_time_ms: Optional[int]
    total_ratings: int
    fulfillment_rate: float
    buyer_diversity: int


class ContextQualityDetailResponse(BaseModel):
    """Extended context quality with component score breakdown."""
    listing_id: str
    status: str
    quality_tier: str
    tier_label: str
    quality_score: Optional[float]
    avg_semantic_relevance: Optional[float]
    avg_rating: Optional[float]
    avg_response_time_ms: Optional[int]
    total_ratings: int
    fulfillment_rate: float
    buyer_diversity: int
    updated_at: Optional[str] = None


class ContextQualityListingItem(BaseModel):
    """A single listing with quality data for discovery/search."""
    listing_id: str
    title: str
    category: Optional[str]
    agent_id: str
    agent_name: str
    quality_score: Optional[float]
    quality_tier: str
    avg_semantic_relevance: Optional[float]
    avg_rating: Optional[float]
    avg_response_time_ms: Optional[int]
    total_ratings: int
    fulfillment_rate: float
    buyer_diversity: int
    updated_at: Optional[str] = None
