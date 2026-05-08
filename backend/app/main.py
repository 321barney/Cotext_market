from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
import uuid
from datetime import datetime, timedelta
import hashlib
import os

from app.database import db
from app.auth import generate_api_key, get_agent_from_api_key
from app.embeddings import embed_text, chunk_text
from app.search import search_knowledge
from app.synthesis import synthesize_answer
from app.theft_protection import check_rate_limit, check_query_fingerprint, watermark_answer
from app.reputation import update_seller_reputation
from app.payments import receive_payment, settle_query, refund_query
from app.config import get_settings

settings = get_settings()

# Conditionally enable docs based on DEBUG
app = FastAPI(
    title="Context Market",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", settings.app_url).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Load escrow contract address
ESCROW_CONTRACT = settings.escrow_contract_address if hasattr(settings, 'escrow_contract_address') else None

# Registration rate limit: IP → {count, reset_at}
_registration_limit = {}
REGISTRATION_LIMIT = 5  # per hour per IP

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

# ======================
# Startup / Shutdown
# ======================

@app.on_event("startup")
async def startup():
    await db.connect()
    
    # Security: warn if DEBUG is enabled in production
    if settings.debug:
        import logging
        logger = logging.getLogger("main")
        logger.warning("⚠️  DEBUG=true — Stack traces will expose sensitive data. Disable in production.")

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

class AgentRegisterResponse(BaseModel):
    agent_id: str
    name: str
    api_key: str
    created_at: datetime

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

    api_key, key_hash = generate_api_key()

    agent = await db.fetchrow(
        """
        INSERT INTO agents (name, api_key_hash, wallet_address, wallet_chain)
        VALUES ($1, $2, $3, $4)
        RETURNING id, name, created_at
        """,
        req.name, key_hash, req.wallet_address, req.wallet_chain
    )

    return AgentRegisterResponse(
        agent_id=str(agent["id"]),
        name=agent["name"],
        api_key=api_key,
        created_at=agent["created_at"]
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
    # Validate seller has wallet
    if not agent.get("wallet_address"):
        raise HTTPException(
            status_code=400,
            detail="Set wallet before creating listings. POST /agent/wallet first."
        )

    chunks = chunk_text(req.knowledge_text)

    listing = await db.fetchrow(
        """
        INSERT INTO memory_listings
            (agent_id, title, description, category, price_per_query, query_limit_per_day, raw_knowledge_text)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        agent["id"], req.title, req.description, req.category,
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
    2. Second call (with query_id): Verifies deposit, delivers answer, sets release_at = now + 24h
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

    # Check rate limit
    allowed, retry_after = await check_rate_limit(buyer_id, listing["id"])
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds."
        )

    # Check query fingerprint (theft protection) - keyed to wallet
    question_embedding = await embed_text(req.question)
    is_duplicate = await check_query_fingerprint(agent.get("wallet_address") or buyer_id, question_embedding)
    if is_duplicate:
        raise HTTPException(status_code=429, detail="Similar query already asked recently")

    # Check if this is a follow-up call (buyer sent query_id in header)
    existing_query_id = request.headers.get("X-Query-ID")

    if existing_query_id:
        # === STEP 2: Buyer has deposited, verify and deliver ===
        query_record = await db.fetchrow(
            "SELECT id, status, cost, release_at FROM queries WHERE id = $1 AND buyer_agent_id = $2",
            _parse_uuid(existing_query_id, "query_id"), buyer_id
        )

        if not query_record:
            raise HTTPException(status_code=404, detail="Query not found")

        if query_record["status"] == "completed":
            # Already answered, return cached answer
            return await _get_query_response(query_record["id"])

        # Verify payment on-chain
        confirmed, msg = await receive_payment(buyer_wallet, query_record["cost"], existing_query_id)

        if not confirmed:
            raise HTTPException(status_code=402, detail=f"Payment not confirmed: {msg}")

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
            # Another request already processing this query
            raise HTTPException(status_code=409, detail="Query already being processed")

        payment_verified_at = datetime.utcnow()

        # Payment verified - proceed with search and synthesis
        return await _process_and_deliver(
            query_record["id"], req.question, listing["id"], seller_id,
            listing["seller_name"], price, question_embedding, buyer_id, payment_verified_at
        )

    # === STEP 1: Create query, return payment instructions ===
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

    # Return payment instructions
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
    chunks = await search_knowledge(listing_id, question, top_k=3)

    if not chunks:
        answer = "I don't have specific knowledge about that in my context."
        confidence = 0.0
    else:
        answer, confidence = await synthesize_answer(question, chunks)

    # Compute response time
    response_time_ms = int((datetime.utcnow() - payment_verified_at).total_seconds() * 1000)

    # Compute semantic relevance (Q→A cosine similarity)
    semantic_relevance = 0.0
    if answer and len(answer) > 10:
        try:
            answer_embedding = await embed_text(answer[:500])  # embed first 500 chars
            semantic_relevance = _cosine_similarity(question_embedding, answer_embedding)
        except Exception:
            pass  # Don't fail the query if embedding fails

    # Watermark answer
    watermarked_answer = watermark_answer(answer, buyer_id)

    # Set release_at = now + 24 hours (dispute window)
    release_at = datetime.utcnow() + timedelta(hours=24)

    # Build answer embedding string for storage
    answer_embedding_str = None
    if answer and len(answer) > 10:
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
        "SELECT COUNT(*) FROM queries WHERE buyer_agent_id = $1 AND status = 'completed'",
        agent["id"]
    ) or 0

    total_earnings = await db.fetchval(
        """
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE agent_id = $1 AND type = 'query_earn'
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
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0", "payment_mode": "escrow"}

# ======================
# 10. Dispute Endpoint
# ======================

@app.post("/query/dispute")
async def dispute_query(
    query_id: str,
    reason: str,
    agent: dict = Depends(get_agent_from_api_key)
):
    """
    File a dispute within 24h of query delivery.
    Halts settlement until resolved.
    """
    query_uuid = _parse_uuid(query_id, "query_id")

    query = await db.fetchrow(
        """
        SELECT id, status, release_at, buyer_agent_id
        FROM queries
        WHERE id = $1
        """,
        query_uuid
    )

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    if str(query["buyer_agent_id"]) != str(agent["id"]):
        raise HTTPException(status_code=403, detail="Not your query")

    if query["status"] not in ('pending', 'completed'):
        raise HTTPException(status_code=400, detail="Query not in pending/completed status")

    # Check 24h window
    if query["release_at"] and query["release_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Dispute window expired (24h)")

    # Create dispute
    await db.execute(
        """
        INSERT INTO disputes (query_id, reason)
        VALUES ($1, $2)
        """,
        query_uuid, reason
    )

    # Mark query as disputed
    await db.execute(
        "UPDATE queries SET disputed = true WHERE id = $1",
        query_uuid
    )

    return {
        "status": "disputed",
        "query_id": query_id,
        "reason": reason,
        "message": "Settlement halted. Awaiting resolution."
    }

# ======================
# 11. Dispute Resolution (Admin)
# ======================

@app.post("/query/dispute/resolve")
async def resolve_dispute(
    query_id: str,
    resolution: str,  # 'refund' or 'release'
    agent: dict = Depends(get_agent_from_api_key)
):
    """
    Resolve a dispute. Only the seller of the disputed listing can resolve.
    'refund' → returns USDC to buyer
    'release' → proceeds with settlement
    """
    # Validate UUID
    query_uuid = _parse_uuid(query_id, "query_id")

    # Get dispute + listing info
    dispute = await db.fetchrow(
        """
        SELECT d.id, d.query_id, q.listing_id, q.buyer_agent_id, m.agent_id as seller_id
        FROM disputes d
        JOIN queries q ON q.id = d.query_id
        JOIN memory_listings m ON m.id = q.listing_id
        WHERE d.query_id = $1 AND d.resolution IS NULL
        """,
        query_uuid
    )

    if not dispute:
        raise HTTPException(status_code=404, detail="No active dispute found")

    # Auth check: only seller can resolve
    if str(dispute["seller_id"]) != str(agent["id"]):
        raise HTTPException(
            status_code=403,
            detail="Only the seller of this listing can resolve disputes"
        )

    if resolution not in ("refund", "release"):
        raise HTTPException(status_code=400, detail="Resolution must be 'refund' or 'release'")

    # Resolve
    await db.execute(
        """
        UPDATE disputes
        SET resolution = $1, resolved_at = NOW()
        WHERE query_id = $2
        """,
        resolution, query_uuid
    )

    if resolution == "refund":
        # Get buyer wallet
        buyer = await db.fetchrow(
            "SELECT wallet_address FROM agents WHERE id = $1",
            dispute["buyer_agent_id"]
        )

        if buyer and buyer["wallet_address"]:
            success, result = await refund_query(query_id, buyer["wallet_address"])
            if success:
                # Update query status
                await db.execute(
                    "UPDATE queries SET status = 'refunded' WHERE id = $1",
                    query_uuid
                )
                return {"status": "refunded", "query_id": query_id, "tx_hash": result}
            else:
                return {"status": "refund_failed", "error": result}
        else:
            return {"status": "refund_failed", "error": "Buyer has no wallet"}

    elif resolution == "release":
        # Mark as pending, scheduler will settle
        await db.execute(
            "UPDATE queries SET disputed = false, status = 'pending' WHERE id = $1",
            query_uuid
        )
        return {"status": "released", "query_id": query_id, "message": "Will settle on next scheduler run"}

    else:
        raise HTTPException(status_code=400, detail="Resolution must be 'refund' or 'release'")
