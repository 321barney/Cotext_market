from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# ======================
# Request Schemas
# ======================

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    wallet_address: Optional[str] = Field(None, pattern=r"^0x[a-fA-F0-9]{40}$")
    wallet_chain: Optional[str] = Field("base", pattern=r"^(base|base-sepolia)$")

class MemoryStoreRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: str = Field(..., min_length=1, max_length=50)
    knowledge_text: str = Field(..., min_length=10, max_length=100000)
    price_per_query: Decimal = Field(..., ge=0.01, le=100.00)
    query_limit_per_day: int = Field(100, ge=1, le=10000)

class MemoryQueryRequest(BaseModel):
    listing_id: str
    question: str = Field(..., min_length=1, max_length=1000)

class RateQueryRequest(BaseModel):
    query_id: str
    score: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=500)

class CreditPurchaseRequest(BaseModel):
    amount_cents: int = Field(..., ge=100, le=1000000)  # $1.00 to $10,000

# ======================
# Response Schemas
# ======================

class AgentRegisterResponse(BaseModel):
    agent_id: str
    name: str
    api_key: str  # shown once, never again
    created_at: datetime

class MemoryListingResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    title: str
    description: Optional[str]
    category: str
    price_per_query: Decimal
    total_queries: int
    reputation_score: Optional[float]  # null if <10 ratings
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

class ErrorResponse(BaseModel):
    error: str
    code: str
    detail: Optional[str] = None
