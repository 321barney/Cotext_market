from fastapi import FastAPI, Depends, HTTPException, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from decimal import Decimal
import asyncio
import uuid
from datetime import datetime, timedelta
import hashlib
import os
import logging

from app.database import db
from app.auth import generate_api_key, get_agent_from_api_key
from app.embeddings import embed_text, chunk_text
from app.search import search_knowledge
from app.synthesis import synthesize_answer
from app.theft_protection import check_rate_limit, check_query_fingerprint, watermark_answer
from app.reputation import update_seller_reputation
from app.payments import receive_payment, settle_query, refund_query
from app.config import get_settings
from app.models import (
    CAPABILITY_TAXONOMY,
    TRUSTED_AGENT_TYPES,
    AUTO_VERIFY_TYPES,
    AgentVerifyRequest,
    AgentVerifyResponse,
    AgentInfoResponse,
    CapabilityListResponse,
    CapabilityTaxonomyItem,
    DiscoveryAgentItem,
    AgentDiscoveryResponse,
    AgentManifestResponse,
    ManifestInfo,
    ManifestPayment,
    ManifestVerification,
    TransactionListResponse,
    TransactionItem,
    TransactionSummary,
    DisputeRequest,
    DisputeResponse,
)
from app.transactions import (
    record_transaction,
    get_agent_transactions,
    get_transaction_summary,
    open_dispute,
    resolve_dispute as resolve_dispute_tx,
    get_dispute_by_query,
    record_payment_transaction,
    record_delivery_transaction,
    record_settlement_transaction,
)

logger = logging.getLogger("main")
settings = get_settings()

# Conditionally enable docs based on DEBUG
app = FastAPI(
    title="Context Market",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS
ALLOWED_ORIGINS = (os.getenv("ALLOWED_ORIGINS") or settings.app_url or "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Serve static files (robots.txt, sitemap.xml)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Load escrow contract address
ESCROW_CONTRACT = settings.escrow_contract_address if hasattr(settings, 'escrow_contract_address') else None

# Parse allowed agent types from config (supports List[str] or comma-separated string)
_agent_types_raw = getattr(settings, 'allowed_agent_types', ['custom', 'unknown', 'langchain', 'crewai', 'autogen'])
if isinstance(_agent_types_raw, str):
    ALLOWED_AGENT_TYPES = set(t.strip().lower() for t in _agent_types_raw.split(',') if t.strip())
else:
    ALLOWED_AGENT_TYPES = set(t.strip().lower() for t in _agent_types_raw if t.strip())

REQUIRE_AGENT_VERIFICATION = getattr(settings, 'require_agent_verification', False)

# Registration rate limit: IP -> {count, reset_at}
_registration_limit = {}
REGISTRATION_LIMIT = settings.registration_limit_per_hour  # per hour per IP


# ======================
# Helpers
# ======================

def _parse_uuid(value: str, field_name: str = "id") -> uuid.UUID:
    """Safely parse UUID, return 400 on invalid format."""
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

def _mask_wallet(addr: str) -> str:
    """Mask wallet address for logging: 0x1234...5678"""
    if not addr or len(addr) < 10:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"

def _check_registration_rate_limit(client_ip: str):
    """Check IP-based registration rate limit."""
    now = datetime.utcnow()
    entry = _registration_limit.get(client_ip)

    if entry and entry["reset_at"] > now:
        if entry["count"] >= REGISTRATION_LIMIT:
            retry_after = int((entry["reset_at"] - now).total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Registration limit exceeded. Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)}
            )
        entry["count"] += 1
    else:
        _registration_limit[client_ip] = {
            "count": 1,
            "reset_at": now + timedelta(hours=1)
        }

def _validate_agent_type(agent_type: str) -> str:
    """Validate and normalize agent type. Returns normalized type or raises."""
    normalized = agent_type.strip().lower()
    if normalized not in ALLOWED_AGENT_TYPES:
        allowed_list = ', '.join(sorted(ALLOWED_AGENT_TYPES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_type '{agent_type}'. Allowed: {allowed_list}"
        )
    return normalized

def _determine_verification(agent_type: str) -> tuple:
    """
    Determine verification status based on agent type.
    Returns (verified: bool, method: str)
    """
    if agent_type in AUTO_VERIFY_TYPES:
        # Simple types auto-verify
        return True, "auto"
    elif agent_type in TRUSTED_AGENT_TYPES:
        # Trusted types: check it's in allowed list (challenge response TBD)
        return True, "auto"
    else:
        # Any other valid type
        return True, "auto"


# ======================
# Startup / Shutdown
# ======================

@app.on_event("startup")
async def startup():
    # Connect synchronously — requests must not arrive before the pool is ready.
    # The pool uses min_size=2 so this is fast and doesn't hammer the DB.
    try:
        await db.connect()
        logger.info("Database pool ready.")
    except Exception as e:
        # Log but don't crash — _require_pool() returns 503 until reconnected.
        logger.error(f"Database connection failed at startup: {e}")

    if settings.debug:
        logger.warning("DEBUG=true — disable in production.")

    if REQUIRE_AGENT_VERIFICATION:
        logger.info("Agent verification is ENABLED.")

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


# ======================
# Pydantic Models
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


class AgentRegisterResponse(BaseModel):
    agent_id: str
    name: str
    api_key: str
    created_at: datetime
    agent_type: str = "unknown"
    agent_capabilities: List[str] = []
    verified_agent: bool = False
    verification_method: Optional[str] = None


class MemoryStoreRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    knowledge_text: str = Field(..., min_length=10)
    price_per_query: Decimal = Field(..., ge=0.01)
    query_limit_per_day: int = Field(default=100, ge=1)


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


class MemoryQueryRequest(BaseModel):
    listing_id: str
    question: str = Field(..., min_length=1, max_length=1000)


class MemoryQueryResponse(BaseModel):
    query_id: str
    answer: str
    cost: Decimal
    confidence: float
    seller_id: str
    seller_name: str
    created_at: datetime
    escrow_address: Optional[str] = None
    payment_status: Optional[str] = None


class WalletSetupRequest(BaseModel):
    wallet_address: str
    chain: str = "base"


class WalletSetupResponse(BaseModel):
    wallet_address: str
    chain: str
    status: str


class AgentEarningsResponse(BaseModel):
    agent_id: str
    name: str
    credit_balance: Decimal
    earnings_balance: Decimal
    total_queries_served: int
    total_earnings: Decimal


class QueryRateRequest(BaseModel):
    query_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None


# ======================
# 1. Register Agent
# ======================

@app.post("/agent/register", response_model=AgentRegisterResponse)
async def register_agent(req: AgentRegisterRequest, request: Request):
    # Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    _check_registration_rate_limit(client_ip)

    # Validate agent_type against allowed types
    agent_type = _validate_agent_type(req.agent_type)

    # Validate capabilities against taxonomy (warn for unknown, but allow)
    validated_capabilities = []
    for cap in req.agent_capabilities:
        cap_clean = cap.strip().lower()
        if cap_clean:
            if cap_clean not in CAPABILITY_TAXONOMY:
                logger.warning(f"Agent registration with non-standard capability: '{cap_clean}' from IP {client_ip}")
            validated_capabilities.append(cap_clean)

    # Determine verification status
    verified, verification_method = _determine_verification(agent_type)

    # If require_agent_verification is enabled and type doesn't auto-verify,
    # mark as unverified
    final_verified = verified
    if REQUIRE_AGENT_VERIFICATION and agent_type in TRUSTED_AGENT_TYPES:
        # In strict mode, trusted types need manual verification too
        final_verified = False
        verification_method = "pending"

    api_key, key_hash = generate_api_key()

    agent = await db.fetchrow(
        """
        INSERT INTO agents (
            name, api_key_hash, wallet_address, wallet_chain,
            agent_type, agent_capabilities, agent_version, agent_endpoint,
            verified_agent, verification_method
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id, name, created_at
        """,
        req.name, key_hash, req.wallet_address, req.wallet_chain,
        agent_type, validated_capabilities, req.agent_version, req.agent_endpoint,
        final_verified, verification_method
    )

    logger.info(
        f"Agent registered: id={agent['id']}, type={agent_type}, "
        f"verified={final_verified}, method={verification_method}, ip={client_ip}"
    )

    return AgentRegisterResponse(
        agent_id=str(agent["id"]),
        name=agent["name"],
        api_key=api_key,
        created_at=agent["created_at"],
        agent_type=agent_type,
        agent_capabilities=validated_capabilities,
        verified_agent=final_verified,
        verification_method=verification_method
    )


# ======================
# 2. Store Memory
# ======================

@app.post("/memory/store")
async def store_memory(
    req: MemoryStoreRequest,
    agent: dict = Depends(get_agent_from_api_key)
):
    """Upload knowledge text, chunk it, embed it, create listing."""
    seller_id = agent.get("id")
    seller_name = agent.get("name", "unknown")

    # Validate seller has wallet
    if not agent.get("wallet_address"):
        raise HTTPException(
            status_code=400,
            detail="Set wallet before creating listings. POST /agent/wallet first."
        )

    # Seller verification check
    is_verified = agent.get("verified_agent", False)
    if not is_verified:
        logger.warning(
            f"Unverified agent '{seller_name}' ({seller_id}) attempting to store memory. "
            f"verification_method={agent.get('verification_method', 'none')}"
        )
        if REQUIRE_AGENT_VERIFICATION:
            raise HTTPException(
                status_code=403,
                detail="Agent verification required before storing memories. "
                       "Contact platform admin or POST /agent/verify to request verification."
            )

    chunks = chunk_text(req.knowledge_text)

    listing = await db.fetchrow(
        """
        INSERT INTO memory_listings
            (agent_id, title, description, category, price_per_query, query_limit_per_day, raw_knowledge_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        seller_id, req.title, req.description, req.category,
        req.price_per_query, req.query_limit_per_day, req.knowledge_text
    )

    listing_id = listing["id"]

    for i, chunk_text_content in enumerate(chunks):
        embedding = await embed_text(chunk_text_content)
        embedding_str = '[' + ','.join(str(x) for x in embedding) + ']'
        await db.execute(
            """
            INSERT INTO memory_chunks (listing_id, chunk_text, embedding, chunk_index)
            VALUES ($1, $2, $3::vector, $4)
            """,
            listing_id, chunk_text_content, embedding_str, i
        )

    logger.info(f"Memory stored: listing_id={listing_id}, agent_id={seller_id}, chunks={len(chunks)}")

    return {
        "listing_id": str(listing_id),
        "chunks_stored": len(chunks),
        "status": "active"
    }


# ======================
# 3. List Memory
# ======================

@app.get("/memory/list", response_model=List[MemoryListingResponse])
async def list_memory(
    category: Optional[str] = None,
    agent: dict = Depends(get_agent_from_api_key)
):
    """Browse active listings."""
    if category:
        rows = await db.fetch(
            """
            SELECT m.id, m.agent_id, m.title, m.description, m.category,
                   m.price_per_query, m.total_queries, m.created_at, a.name as agent_name,
                   sr.composite_score as reputation_score, sr.tier
            FROM memory_listings m
            JOIN agents a ON m.agent_id = a.id
            LEFT JOIN seller_reputation sr ON sr.seller_agent_id = m.agent_id
            WHERE m.is_active = TRUE AND m.category = $1
            ORDER BY COALESCE(sr.composite_score, 0) DESC, m.total_queries DESC
            """,
            category
        )
    else:
        rows = await db.fetch(
            """
            SELECT m.id, m.agent_id, m.title, m.description, m.category,
                   m.price_per_query, m.total_queries, m.created_at, a.name as agent_name,
                   sr.composite_score as reputation_score, sr.tier
            FROM memory_listings m
            JOIN agents a ON m.agent_id = a.id
            LEFT JOIN seller_reputation sr ON sr.seller_agent_id = m.agent_id
            WHERE m.is_active = TRUE
            ORDER BY COALESCE(sr.composite_score, 0) DESC, m.total_queries DESC
            """
        )

    return [
        MemoryListingResponse(
            id=str(r["id"]), agent_id=str(r["agent_id"]), agent_name=r["agent_name"],
            title=r["title"], description=r["description"], category=r["category"],
            price_per_query=r["price_per_query"], total_queries=r["total_queries"],
            reputation_score=r["reputation_score"], created_at=r["created_at"]
        ) for r in rows
    ]


# ======================
# 4. Query Memory (Escrow Flow)
# ======================

@app.post("/memory/query", response_model=MemoryQueryResponse)
async def query_memory(
    req: MemoryQueryRequest,
    request: Request,
    agent: dict = Depends(get_agent_from_api_key)
):
    """
    Escrow payment flow:
    1. First call: Returns escrow address + amount + query_id (buyer deposits USDC)
    2. Second call (with query_id): Verifies deposit, delivers answer, sets release_at = now + dispute_window_hours
    3. Scheduler settles after 24h (90% seller, 10% platform)
    """
    buyer_id = agent["id"]
    buyer_wallet = agent.get("wallet_address")

    # Get listing details
    listing = await db.fetchrow(
        """
        SELECT m.id, m.agent_id, m.price_per_query, a.name as seller_name, a.wallet_address
        FROM memory_listings m
        JOIN agents a ON m.agent_id = a.id
        WHERE m.id = $1 AND m.is_active = TRUE
        """,
        _parse_uuid(req.listing_id, "listing_id")
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or inactive")

    seller_id = listing["agent_id"]

    # Self-query prevention
    if str(seller_id) == str(buyer_id):
        raise HTTPException(status_code=400, detail="Cannot query your own listing")

    price = listing["price_per_query"]
    seller_wallet = listing["wallet_address"]

    if not seller_wallet:
        raise HTTPException(status_code=400, detail="Seller has no wallet configured")

    if not buyer_wallet:
        raise HTTPException(status_code=400, detail="Buyer has no wallet configured")

    # Determine which step this is before running step-1-only checks.
    existing_query_id = request.headers.get("X-Query-ID")

    if existing_query_id:
        # === STEP 2: Buyer has deposited — verify payment and deliver answer ===
        # Skip rate-limit and fingerprint: those were enforced in step 1.
        query_record = await db.fetchrow(
            "SELECT id, status, cost, release_at FROM queries WHERE id = $1 AND buyer_agent_id = $2",
            _parse_uuid(existing_query_id, "query_id"), buyer_id
        )

        if not query_record:
            raise HTTPException(status_code=404, detail="Query not found")

        if query_record["status"] in ("pending", "settled", "delivered"):
            # Already answered — return cached response
            return await _get_query_response(str(query_record["id"]))

        # Verify payment on-chain
        confirmed, msg = await receive_payment(buyer_wallet, query_record["cost"], existing_query_id)
        if not confirmed:
            raise HTTPException(status_code=402, detail=f"Payment not confirmed: {msg}")

        # Record payment transaction (immutable audit trail)
        try:
            await record_payment_transaction(
                query_id=str(query_record["id"]),
                buyer_id=str(buyer_id),
                seller_id=str(seller_id),
                listing_id=str(listing["id"]),
                cost=price
            )
        except Exception as e:
            logger.warning(f"Failed to record payment transaction: {e}")

        # ATOMIC: mark as processing to prevent race condition
        updated = await db.fetchval(
            """
            UPDATE queries
            SET status = 'processing', payment_verified_at = NOW()
            WHERE id = $1 AND status = 'payment_required'
            RETURNING id
            """,
            query_record["id"]
        )

        if not updated:
            raise HTTPException(status_code=409, detail="Query already being processed")

        payment_verified_at = datetime.utcnow()
        question_embedding = await embed_text(req.question)

        return await _process_and_deliver(
            query_record["id"], req.question, listing["id"], seller_id,
            listing["seller_name"], price, question_embedding, buyer_id, payment_verified_at
        )

    # === STEP 1: Enforce limits, embed question, return payment instructions ===

    # Rate limit: max queries per buyer per listing per day
    allowed, retry_after = await check_rate_limit(buyer_id, listing["id"])
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds."
        )

    # Embed question and check for near-duplicate queries (theft protection)
    question_embedding = await embed_text(req.question)
    is_duplicate = await check_query_fingerprint(agent.get("wallet_address") or str(buyer_id), question_embedding)
    if is_duplicate:
        raise HTTPException(status_code=429, detail="Similar query already asked recently")

    question_embedding_str = '[' + ','.join(str(x) for x in question_embedding) + ']'

    query_record = await db.fetchrow(
        """
        INSERT INTO queries (buyer_agent_id, listing_id, question, question_embedding, cost, status)
        VALUES ($1, $2, $3, $4::vector, $5, 'payment_required')
        RETURNING id, created_at
        """,
        buyer_id, listing["id"], req.question, question_embedding_str, price
    )

    query_id = str(query_record["id"])

    return MemoryQueryResponse(
        query_id=query_id,
        answer="",
        cost=price,
        confidence=0.0,
        seller_id=str(seller_id),
        seller_name=listing["seller_name"],
        created_at=query_record["created_at"],
        escrow_address=ESCROW_CONTRACT,
        payment_status="PAYMENT_REQUIRED"
    )

async def _process_and_deliver(
    query_id: str, question: str, listing_id: uuid.UUID,
    seller_id: uuid.UUID, seller_name: str, price: Decimal,
    question_embedding, buyer_id: str, payment_verified_at: datetime
):
    """Search knowledge, synthesize answer, compute metrics, update query record."""
    # Search knowledge
    chunks = await search_knowledge(listing_id, question, top_k=settings.top_k_chunks)

    if not chunks:
        answer = "I don't have specific knowledge about that in my context."
        confidence = 0.0
    else:
        answer, confidence = await synthesize_answer(question, chunks)

    # Compute response time
    response_time_ms = int((datetime.utcnow() - payment_verified_at).total_seconds() * 1000)

    # Compute semantic relevance (Q->A cosine similarity)
    semantic_relevance = 0.0
    answer_embedding = None
    if answer and len(answer) > 10:
        try:
            answer_embedding = await embed_text(answer[:500])  # embed first 500 chars
            semantic_relevance = _cosine_similarity(question_embedding, answer_embedding)
        except Exception:
            pass  # Don't fail the query if embedding fails

    # Watermark answer
    watermarked_answer = watermark_answer(answer, buyer_id)

    # Set release_at = now + dispute window hours
    release_at = datetime.utcnow() + timedelta(hours=settings.dispute_window_hours)

    # Build answer embedding string for storage
    answer_embedding_str = None
    if answer_embedding:
        try:
            answer_embedding_str = '[' + ','.join(str(x) for x in answer_embedding) + ']'
        except Exception:
            pass

    # Complete query
    await db.execute(
        """
        UPDATE queries
        SET status = 'pending',
            answer = $1,
            completed_at = NOW(),
            release_at = $2,
            response_time_ms = $3,
            semantic_relevance = $4,
            answer_embedding = $5::vector
        WHERE id = $6
        """,
        watermarked_answer, release_at, response_time_ms,
        round(semantic_relevance, 2) if semantic_relevance else None,
        answer_embedding_str, uuid.UUID(query_id)
    )

    # Update listing stats
    await db.execute(
        "UPDATE memory_listings SET total_queries = total_queries + 1 WHERE id = $1",
        listing_id
    )

    # Record delivery transaction (immutable audit trail)
    try:
        await record_delivery_transaction(
            query_id=query_id,
            buyer_id=str(buyer_id),
            seller_id=str(seller_id),
            listing_id=str(listing_id),
            cost=price
        )
    except Exception as e:
        logger.warning(f"Failed to record delivery transaction: {e}")

    return MemoryQueryResponse(
        query_id=query_id,
        answer=watermarked_answer,
        cost=price,
        confidence=confidence,
        seller_id=str(seller_id),
        seller_name=seller_name,
        created_at=datetime.utcnow(),
        payment_status="DELIVERED_PENDING_SETTLEMENT"
    )

def _cosine_similarity(a: list, b: list) -> float:
    """Calculate cosine similarity between two vectors."""
    import math
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

async def _get_query_response(query_id: str):
    """Return cached query response."""
    query_uuid = _parse_uuid(query_id, "query_id")
    query = await db.fetchrow(
        """
        SELECT q.id, q.answer, q.cost, q.confidence, q.created_at, q.status,
               a.name as seller_name, m.agent_id as seller_id
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        JOIN agents a ON a.id = m.agent_id
        WHERE q.id = $1
        """,
        query_uuid
    )

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    return MemoryQueryResponse(
        query_id=query_id,
        answer=query["answer"],
        cost=query["cost"],
        confidence=query["confidence"] or 0.0,
        seller_id=str(query["seller_id"]),
        seller_name=query["seller_name"],
        created_at=query["created_at"],
        payment_status=query["status"]
    )


# ======================
# 5. Agent Earnings
# ======================

@app.get("/agent/earnings", response_model=AgentEarningsResponse)
async def get_earnings(agent: dict = Depends(get_agent_from_api_key)):
    """View earnings from query payments."""
    total_queries = await db.fetchval(
        """
        SELECT COUNT(DISTINCT query_id) FROM transaction_history
        WHERE seller_agent_id = $1 AND type = 'settlement' AND status = 'completed'
        """,
        agent["id"]
    ) or 0

    total_earnings = await db.fetchval(
        """
        SELECT COALESCE(SUM(amount_usdc - fee_usdc), 0) FROM transaction_history
        WHERE seller_agent_id = $1 AND type = 'settlement' AND status = 'completed'
        """,
        agent["id"]
    ) or Decimal("0")

    return AgentEarningsResponse(
        agent_id=str(agent["id"]),
        name=agent["name"],
        credit_balance=agent.get("credit_balance", Decimal("0")),
        earnings_balance=agent.get("earnings_balance", Decimal("0")),
        total_queries_served=total_queries,
        total_earnings=total_earnings
    )


# ======================
# 6. Query Rating
# ======================

@app.post("/query/rate")
async def rate_query(
    req: QueryRateRequest,
    agent: dict = Depends(get_agent_from_api_key)
):
    """Rate a query response (1-5 stars)."""
    query_uuid = _parse_uuid(req.query_id, "query_id")

    query = await db.fetchrow(
        "SELECT id, listing_id FROM queries WHERE id = $1 AND buyer_agent_id = $2",
        query_uuid, agent["id"]
    )

    if not query:
        raise HTTPException(status_code=404, detail="Query not found or not yours")

    # Get seller
    listing = await db.fetchrow(
        "SELECT agent_id FROM memory_listings WHERE id = $1",
        query["listing_id"]
    )

    seller_id = listing["agent_id"]

    # Insert rating
    await db.execute(
        """
        INSERT INTO ratings (query_id, seller_agent_id, buyer_agent_id, score, comment)
        VALUES ($1, $2, $3, $4, $5)
        """,
        query_uuid, seller_id, agent["id"], req.rating, req.feedback
    )

    # Update reputation (full composite recalculation)
    from app.reputation import update_seller_reputation
    await update_seller_reputation(seller_id)

    return {"status": "rated", "rating": req.rating}


# ======================
# 7. Wallet Setup
# ======================

@app.post("/agent/wallet")
async def set_wallet(
    req: WalletSetupRequest,
    agent: dict = Depends(get_agent_from_api_key)
):
    """Set EVM wallet address for escrow payments."""
    if not req.wallet_address.startswith("0x") or len(req.wallet_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid EVM wallet address")

    await db.execute(
        """
        UPDATE agents
        SET wallet_address = $1, wallet_chain = $2, updated_at = NOW()
        WHERE id = $3
        """,
        req.wallet_address.lower(), req.chain, agent["id"]
    )

    return WalletSetupResponse(
        wallet_address=req.wallet_address.lower(),
        chain=req.chain,
        status="active"
    )

@app.get("/agent/wallet")
async def get_wallet(agent: dict = Depends(get_agent_from_api_key)):
    """Get agent's wallet address."""
    return {
        "wallet_address": agent.get("wallet_address"),
        "chain": agent.get("wallet_chain", "base")
    }


# ======================
# 8. Reputation
# ======================

@app.get("/agent/reputation")
async def get_reputation(agent: dict = Depends(get_agent_from_api_key)):
    """View full reputation profile with composite score and tier."""
    from app.reputation import get_seller_reputation
    rep = await get_seller_reputation(agent["id"])
    return rep


# ======================
# 9. Health Check
# ======================

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring."""
    db_healthy = await db.health_check()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": "2.0.0",
        "payment_mode": "escrow",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/robots.txt")
async def robots_txt():
    return FileResponse("app/static/robots.txt")

@app.get("/sitemap.xml")
async def sitemap_xml():
    return FileResponse("app/static/sitemap.xml")

@app.get("/skill.md", include_in_schema=False)
async def skill_md():
    """Machine-readable agent onboarding guide — agents fetch this to self-register."""
    from fastapi.responses import PlainTextResponse
    import pathlib
    path = pathlib.Path("skill.md")
    if not path.exists():
        path = pathlib.Path("app/skill.md")
    if not path.exists():
        return PlainTextResponse("# skill.md\nSee https://cotrader.cc/docs", media_type="text/markdown")
    return PlainTextResponse(path.read_text(), media_type="text/markdown")


# ======================
# 10. Agent Capabilities
# ======================

@app.get("/agent/capabilities", response_model=CapabilityListResponse)
async def list_capabilities():
    """List all available capability taxonomy entries."""
    # Try to fetch from DB first (migration 002 seeds the table)
    try:
        rows = await db.fetch(
            """
            SELECT name, display_name, description
            FROM capability_taxonomy
            ORDER BY display_name
            """
        )
        if rows:
            capabilities = [
                CapabilityTaxonomyItem(
                    name=r["name"],
                    display_name=r["display_name"],
                    description=r["description"]
                )
                for r in rows
            ]
            return CapabilityListResponse(capabilities=capabilities)
    except Exception:
        # Table may not exist yet, fall through to static list
        logger.debug("capability_taxonomy table not found, using static list")

    # Fallback: static taxonomy from models.py
    # Map to human-readable display names
    display_names = {
        "text-generation": "Text Generation",
        "code-generation": "Code Generation",
        "image-generation": "Image Generation",
        "audio-generation": "Audio Generation",
        "video-generation": "Video Generation",
        "data-analysis": "Data Analysis",
        "web-search": "Web Search",
        "document-parsing": "Document Parsing",
        "translation": "Translation",
        "summarization": "Summarization",
        "classification": "Classification",
        "embedding": "Embedding",
        "retrieval": "Retrieval",
        "tool-use": "Tool Use",
        "memory": "Memory",
        "planning": "Planning",
        "multi-agent": "Multi-Agent Orchestration",
        "staking": "Staking",
        "trading": "Trading",
        "legal": "Legal",
        "medical": "Medical",
        "customer-support": "Customer Support",
        "education": "Education",
        "research": "Research",
    }

    capabilities = [
        CapabilityTaxonomyItem(
            name=cap,
            display_name=display_names.get(cap, cap),
            description=None
        )
        for cap in CAPABILITY_TAXONOMY
    ]
    return CapabilityListResponse(capabilities=capabilities)


# ======================
# 11. Agent Manifest
# ======================

@app.get("/agent/manifest", response_model=AgentManifestResponse)
async def get_agent_manifest():
    """
    Machine-readable agent capability manifest.
    Returns OpenAPI-style schema with all available endpoints,
    payment configuration, agent types, and verification methods.
    """
    # Resolve the escrow contract address
    escrow_addr = ESCROW_CONTRACT or "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

    return AgentManifestResponse(
        openapi="3.0.0",
        info=ManifestInfo(
            title="Context Market API",
            version="2.0.0",
            description="Agent-to-agent knowledge marketplace"
        ),
        capabilities={
            "register": "/agent/register",
            "store_memory": "/memory/store",
            "list_knowledge": "/memory/list",
            "query_knowledge": "/memory/query",
            "discover_agents": "/agents/discover",
            "check_earnings": "/agent/earnings",
            "check_reputation": "/agent/reputation",
            "rate_response": "/query/rate",
            "file_dispute": "/query/dispute"
        },
        payment=ManifestPayment(
            protocol="escrow",
            chain="base",
            chain_id=8453,
            token="USDC",
            token_contract=escrow_addr
        ),
        agent_types=sorted(list(ALLOWED_AGENT_TYPES)),
        verification=ManifestVerification(
            required=REQUIRE_AGENT_VERIFICATION,
            methods=["auto", "manual", "did"]
        )
    )


# ======================
# 12. Well-Known Agent Manifest
# ======================

@app.get("/.well-known/agent-manifest")
async def well_known_agent_manifest():
    """
    Well-known agent manifest for automated discovery.
    Follows the proposed agent-manifest standard.
    """
    return {
        "schema_version": "1.0",
        "name": "Context Market",
        "description": "Agent-to-agent knowledge marketplace. Sell and buy specialized knowledge.",
        "url": "https://YOUR_DOMAIN",
        "contact_email": "admin@context.market",

        "authentication": {
            "type": "api_key",
            "header": "X-API-Key",
            "register_endpoint": "/agent/register"
        },

        "api": {
            "base_url": "https://YOUR_DOMAIN",
            "openapi_spec": "/openapi.json",
            "version": "2.0.0"
        },

        "marketplace": {
            "type": "knowledge_exchange",
            "currency": {
                "token": "USDC",
                "chain": "base",
                "chain_id": 8453
            },
            "categories": [
                "trading", "legal", "coding", "research", "medical",
                "data-analysis", "text-generation", "image-generation",
                "audio-generation", "video-generation", "translation",
                "summarization", "classification", "customer-support",
                "education", "multi-agent", "planning", "memory",
                "tool-use", "staking"
            ],
            "pricing_model": "per_query",
            "settlement": {
                "type": "escrow",
                "dispute_window_hours": 24,
                "protocol": "smart_contract"
            }
        },

        "agent_requirements": {
            "verification_required": False,
            "supported_types": ["langchain", "crewai", "autogen", "custom"],
            "wallet_required": True,
            "wallet_chain": "base"
        },

        "endpoints": {
            "register": "/agent/register",
            "store_knowledge": "/memory/store",
            "list_knowledge": "/memory/list",
            "query_knowledge": "/memory/query",
            "discover": "/agents/discover",
            "rate": "/query/rate",
            "dispute": "/query/dispute",
            "earnings": "/agent/earnings",
            "reputation": "/agent/reputation",
            "transactions": "/agent/transactions"
        },

        "discovery": {
            "manifest_url": "/.well-known/agent-manifest",
            "capability_taxonomy": "/agent/capabilities",
            "search_endpoint": "/agents/discover",
            "search_parameters": {
                "q": "search term",
                "capability": "filter by capability",
                "agent_type": "filter by agent framework",
                "verified_only": "boolean",
                "min_reputation": "minimum composite score"
            }
        }
    }


# ======================
# 13. Agent Verification (Admin)
# ======================

@app.post("/agent/verify", response_model=AgentVerifyResponse)
async def verify_agent(
    req: AgentVerifyRequest,
    agent: dict = Depends(get_agent_from_api_key)
):
    """
    Manual verification endpoint.
    Platform admin can mark agents as verified.
    Agents can also request self-verification (type must be in allowed list).
    """
    target_agent_id = _parse_uuid(req.agent_id, "agent_id")
    requester_id = agent["id"]

    # Get the target agent
    target = await db.fetchrow(
        """
        SELECT id, name, agent_type, verified_agent, verification_method
        FROM agents WHERE id = $1
        """,
        target_agent_id
    )

    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check authorization: agents can only verify themselves;
    # in a real system, you'd check for admin role here
    can_verify_any = False  # TODO: add admin role check

    if str(target_agent_id) != str(requester_id) and not can_verify_any:
        raise HTTPException(
            status_code=403,
            detail="You can only verify your own agent. Contact platform admin for manual verification."
        )

    # If already verified, return current state
    if target["verified_agent"]:
        return AgentVerifyResponse(
            agent_id=str(target_agent_id),
            verified=True,
            verification_method=target["verification_method"] or "manual",
            verified_at=datetime.utcnow()
        )

    # Validate the agent type is still in allowed list
    agent_type = (target["agent_type"] or "unknown").lower()
    if agent_type not in ALLOWED_AGENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Agent type '{agent_type}' is not in the allowed types list."
        )

    # Perform verification
    verified = True
    method = req.verification_method or "manual"

    await db.execute(
        """
        UPDATE agents
        SET verified_agent = TRUE, verification_method = $1, updated_at = NOW()
        WHERE id = $2
        """,
        method, target_agent_id
    )

    logger.info(f"Agent verified: id={target_agent_id}, type={agent_type}, method={method}")

    return AgentVerifyResponse(
        agent_id=str(target_agent_id),
        verified=verified,
        verification_method=method,
        verified_at=datetime.utcnow()
    )


# ======================
# 13. Agent Discovery (Semantic Search)
# ======================

@app.get("/agents/discover", response_model=AgentDiscoveryResponse)
async def discover_agents(
    q: Optional[str] = Query(None, description="Search term for title, description, or agent name"),
    capability: Optional[str] = Query(None, description="Filter by capability (exact match on agent_capabilities)"),
    agent_type: Optional[str] = Query(None, description="Filter by agent framework type"),
    category: Optional[str] = Query(None, description="Filter by listing category"),
    verified_only: bool = Query(False, description="Only return verified agents"),
    min_reputation: Optional[float] = Query(None, ge=0, le=5, description="Minimum composite reputation score"),
    sort: str = Query("reputation", description="Sort by: reputation, queries, price_asc, price_desc, newest"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Semantic search for agents and listings.

    Supports full-text search across listing titles, descriptions, and agent names.
    Filters by capability, agent type, category, verification status, and reputation.
    Sortable by reputation, query count, price, or recency.
    """
    # Validate and sanitize search term
    search_term = None
    if q:
        search_term = q.strip()
        # Limit search term length to prevent abuse
        if len(search_term) > 200:
            search_term = search_term[:200]
        # Escape special characters that could interfere with ILIKE
        search_term = search_term.replace('%', '\\%').replace('_', '\\_')
        if not search_term:
            search_term = None

    # Validate capability filter
    capability_filter = None
    if capability:
        capability_filter = capability.strip().lower()
        if not capability_filter:
            capability_filter = None

    # Validate agent_type filter
    agent_type_filter = None
    if agent_type:
        agent_type_filter = agent_type.strip().lower()
        if agent_type_filter not in ALLOWED_AGENT_TYPES:
            allowed_list = ', '.join(sorted(ALLOWED_AGENT_TYPES))
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent_type '{agent_type}'. Allowed: {allowed_list}"
            )

    # Validate category filter
    category_filter = None
    if category:
        category_filter = category.strip()
        if not category_filter:
            category_filter = None

    # Validate sort parameter
    valid_sort_orders = {"reputation", "queries", "price_asc", "price_desc", "newest"}
    sort_order = sort.strip().lower()
    if sort_order not in valid_sort_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort '{sort}'. Allowed: {', '.join(sorted(valid_sort_orders))}"
        )

    # Main discovery query with all filters
    rows = await db.fetch(
        """
        SELECT
            m.id as listing_id, m.title, m.description, m.category,
            m.price_per_query, m.total_queries, m.created_at as listing_created_at,
            a.id as agent_id, a.name as agent_name, a.agent_type,
            a.agent_capabilities, a.verified_agent, a.agent_version,
            sr.composite_score as reputation_score, sr.tier
        FROM memory_listings m
        JOIN agents a ON m.agent_id = a.id
        LEFT JOIN seller_reputation sr ON sr.seller_agent_id = a.id
        WHERE m.is_active = TRUE
          AND ($1::text IS NULL OR m.category = $1)
          AND ($2::text IS NULL OR a.agent_type = $2)
          AND ($3::bool = FALSE OR a.verified_agent = TRUE)
          AND ($4::float IS NULL OR sr.composite_score >= $4)
          AND ($5::text IS NULL OR
               m.title ILIKE '%' || $5 || '%' OR
               m.description ILIKE '%' || $5 || '%' OR
               a.name ILIKE '%' || $5 || '%')
          AND ($6::text IS NULL OR $6 = ANY(a.agent_capabilities))
        ORDER BY
            CASE WHEN $7 = 'reputation' THEN COALESCE(sr.composite_score, 0) END DESC,
            CASE WHEN $7 = 'queries'    THEN m.total_queries END DESC,
            CASE WHEN $7 = 'price_asc'  THEN m.price_per_query END ASC,
            CASE WHEN $7 = 'price_desc' THEN m.price_per_query END DESC,
            CASE WHEN $7 = 'newest'     THEN m.created_at END DESC
        LIMIT $8 OFFSET $9
        """,
        category_filter, agent_type_filter, verified_only,
        min_reputation, search_term, capability_filter,
        sort_order, limit, offset
    )

    # Count query for total
    total_count = await db.fetchval(
        """
        SELECT COUNT(*)
        FROM memory_listings m
        JOIN agents a ON m.agent_id = a.id
        LEFT JOIN seller_reputation sr ON sr.seller_agent_id = a.id
        WHERE m.is_active = TRUE
          AND ($1::text IS NULL OR m.category = $1)
          AND ($2::text IS NULL OR a.agent_type = $2)
          AND ($3::bool = FALSE OR a.verified_agent = TRUE)
          AND ($4::float IS NULL OR sr.composite_score >= $4)
          AND ($5::text IS NULL OR
               m.title ILIKE '%' || $5 || '%' OR
               m.description ILIKE '%' || $5 || '%' OR
               a.name ILIKE '%' || $5 || '%')
          AND ($6::text IS NULL OR $6 = ANY(a.agent_capabilities))
        """,
        category_filter, agent_type_filter, verified_only,
        min_reputation, search_term, capability_filter
    )

    agents = []
    for r in rows:
        # Build capabilities list safely (handle None)
        caps = r["agent_capabilities"] or []
        if isinstance(caps, str):
            caps = [c.strip() for c in caps.strip('{}').split(',') if c.strip()]

        agents.append(DiscoveryAgentItem(
            listing_id=str(r["listing_id"]),
            title=r["title"],
            description=r["description"],
            category=r["category"],
            price_per_query=r["price_per_query"],
            total_queries=r["total_queries"],
            created_at=r["listing_created_at"],
            agent_id=str(r["agent_id"]),
            agent_name=r["agent_name"],
            agent_type=r["agent_type"] or "unknown",
            agent_capabilities=list(caps),
            agent_version=r["agent_version"],
            verified_agent=r["verified_agent"] or False,
            reputation_score=float(r["reputation_score"]) if r["reputation_score"] is not None else None,
            tier=r["tier"],
        ))

    return AgentDiscoveryResponse(
        agents=agents,
        total=total_count or 0,
        limit=limit,
        offset=offset
    )


# ======================
# 14. Dispute: Open
# ======================

@app.post("/query/dispute", response_model=DisputeResponse)
async def create_dispute(
    req: DisputeRequest,
    agent: dict = Depends(get_agent_from_api_key)
):
    """
    Open a dispute on a query (must be within dispute window).
    Halts settlement until resolved.
    """
    query_uuid = _parse_uuid(req.query_id, "query_id")

    result = await open_dispute(
        query_id=str(query_uuid),
        buyer_agent_id=str(agent["id"]),
        reason=req.reason,
        evidence=req.evidence
    )

    return DisputeResponse(
        dispute_id=result["dispute_id"],
        query_id=result["query_id"],
        status=result["status"],
        reason=result["reason"],
        refund_amount=result["refund_amount"],
        created_at=result["created_at"],
        resolved_at=result["resolved_at"]
    )


# ======================
# 15. Dispute: Check Status
# ======================

@app.get("/query/dispute/{query_id}")
async def get_dispute(query_id: str, agent: dict = Depends(get_agent_from_api_key)):
    """Get dispute status for a query."""
    query_uuid = _parse_uuid(query_id, "query_id")

    dispute = await get_dispute_by_query(
        query_id=str(query_uuid),
        agent_id=str(agent["id"])
    )

    if not dispute:
        raise HTTPException(status_code=404, detail="No dispute found for this query")

    return dispute


# ======================
# 16. Dispute: Resolve (Admin / Seller)
# ======================

@app.post("/query/dispute/resolve")
async def resolve_dispute_endpoint(
    dispute_id: str,
    resolution: str,  # 'resolved_buyer', 'resolved_seller', 'canceled'
    refund_amount: Decimal = Decimal("0"),
    notes: Optional[str] = None,
    agent: dict = Depends(get_agent_from_api_key)
):
    """
    Resolve a dispute. Platform admin or seller can resolve.
    'resolved_buyer' -> refund buyer
    'resolved_seller' -> release funds to seller
    'canceled' -> cancel dispute, return to pending settlement
    """
    if resolution not in ("resolved_buyer", "resolved_seller", "canceled"):
        raise HTTPException(
            status_code=400,
            detail="Resolution must be 'resolved_buyer', 'resolved_seller', or 'canceled'"
        )

    result = await resolve_dispute_tx(
        dispute_id=dispute_id,
        resolution=resolution,
        refund_amount=refund_amount,
        resolver_id=str(agent["id"]),
        notes=notes
    )

    return result


# ======================
# 17. Agent: Transaction History
# ======================

@app.get("/agent/transactions", response_model=TransactionListResponse)
async def get_transactions(
    role: str = Query("all", pattern="^(all|buyer|seller)$"),
    tx_type: str = None,
    status: str = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    agent: dict = Depends(get_agent_from_api_key)
):
    """Get full transaction history for the authenticated agent."""
    result = await get_agent_transactions(
        agent_id=str(agent["id"]),
        role=role,
        tx_type=tx_type,
        status=status,
        limit=limit,
        offset=offset
    )

    # Build TransactionItem models
    tx_items = []
    for tx in result["transactions"]:
        tx_items.append(TransactionItem(
            id=tx["id"],
            type=tx["type"],
            amount_usdc=tx["amount_usdc"],
            fee_usdc=tx["fee_usdc"],
            status=tx["status"],
            buyer_agent_id=tx["buyer_agent_id"],
            seller_agent_id=tx["seller_agent_id"],
            listing_id=tx["listing_id"],
            query_id=tx["query_id"],
            tx_hash=tx["tx_hash"],
            description=tx["description"],
            metadata=tx["metadata"],
            created_at=tx["created_at"],
            completed_at=tx["completed_at"]
        ))

    return TransactionListResponse(
        transactions=tx_items,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        summary=result["summary"]
    )


# ======================
# 18. Agent: Transaction Summary
# ======================

@app.get("/agent/transactions/summary", response_model=TransactionSummary)
async def get_transaction_summary_endpoint(
    agent: dict = Depends(get_agent_from_api_key)
):
    """Get financial summary as both buyer and seller."""
    result = await get_transaction_summary(str(agent["id"]))
    return TransactionSummary(
        as_buyer=result["as_buyer"],
        as_seller=result["as_seller"],
        this_month=result["this_month"]
    )


# ======================
# 19. Settlement Scheduler (Internal)
# ======================

@app.post("/internal/settle-eligible")
async def settle_eligible_queries(
    admin_key: str = Query(..., description="Admin API key for authorization")
):
    """
    Internal endpoint called by scheduler to settle queries past dispute window.
    Settles all queries where release_at < NOW() and status = 'pending'.
    """
    # Simple auth check (admin key should match environment)
    expected_key = os.getenv("ADMIN_API_KEY")
    if not expected_key or admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    # Find all eligible queries
    eligible = await db.fetch(
        """
        SELECT q.id, q.cost, q.listing_id, q.buyer_agent_id,
               a.wallet_address as seller_wallet
        FROM queries q
        JOIN memory_listings m ON m.id = q.listing_id
        JOIN agents a ON a.id = m.agent_id
        WHERE q.status = 'pending'
          AND q.release_at < NOW()
          AND q.disputed = FALSE
        ORDER BY q.created_at ASC
        LIMIT 100
        """
    )

    settled_count = 0
    failed_count = 0
    results = []

    for row in eligible:
        query_id = str(row["id"])
        cost = row["cost"]
        seller_wallet = row["seller_wallet"]

        if not seller_wallet:
            # Record failed settlement (no seller wallet)
            try:
                await record_transaction(
                    buyer_agent_id=str(row["buyer_agent_id"]),
                    seller_agent_id=str(row["listing_id"]),  # placeholder
                    listing_id=str(row["listing_id"]),
                    query_id=query_id,
                    tx_type="failed",
                    amount_usdc=cost,
                    status="failed",
                    description="Settlement failed: seller has no wallet"
                )
            except Exception as e:
                logger.warning(f"Failed to record failed settlement: {e}")

            await db.execute(
                "UPDATE queries SET status = 'failed' WHERE id = $1",
                row["id"]
            )
            failed_count += 1
            results.append({"query_id": query_id, "status": "failed", "reason": "no_seller_wallet"})
            continue

        # Attempt settlement
        success, result = await settle_query(query_id, seller_wallet, cost)

        if success:
            settled_count += 1
            results.append({"query_id": query_id, "status": "settled", "tx_hash": result})
        else:
            failed_count += 1
            results.append({"query_id": query_id, "status": "failed", "reason": result})

    return {
        "processed": len(eligible),
        "settled": settled_count,
        "failed": failed_count,
        "results": results
    }
