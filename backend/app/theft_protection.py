"""
Theft protection: rate limits, query fingerprinting, watermarking
"""
import hashlib
from datetime import datetime, timedelta
from app.database import db
from app.config import get_settings

settings = get_settings()

async def check_rate_limit(buyer_id: str, listing_id: str) -> tuple:
    """
    Check if buyer has exceeded daily query limit for this listing.
    Returns: (allowed: bool, retry_after_seconds: int)
    """
    # Count queries in last 24 hours
    count = await db.fetchrow(
        """
        SELECT COUNT(*) as query_count
        FROM queries
        WHERE buyer_agent_id = $1 
          AND listing_id = $2
          AND created_at > NOW() - INTERVAL '24 hours'
        """,
        buyer_id, listing_id
    )
    
    query_count = count["query_count"] if count else 0
    
    if query_count >= settings.max_queries_per_day_per_buyer:
        # Get time until oldest query expires
        oldest = await db.fetchrow(
            """
            SELECT created_at FROM queries
            WHERE buyer_agent_id = $1 AND listing_id = $2
            ORDER BY created_at ASC
            LIMIT 1 OFFSET $3
            """,
            buyer_id, listing_id, settings.max_queries_per_day_per_buyer - 1
        )
        
        if oldest:
            retry_after = int((oldest["created_at"] + timedelta(hours=24) - datetime.now()).total_seconds())
            return False, max(retry_after, 0)
        
        return False, 3600  # Default 1 hour
    
    return True, 0

async def check_query_fingerprint(wallet_address: str, question_embedding: list) -> bool:
    """
    Check if this wallet recently asked a very similar question.
    Uses cosine similarity threshold of 0.85.
    Keys on wallet_address (not agent_id) to prevent multi-agent bypass.
    Returns: True if duplicate/similar query found
    """
    if not wallet_address:
        return False
    
    # Get recent queries from this wallet (last 7 days)
    recent_queries = await db.fetch(
        """
        SELECT q.question_embedding
        FROM queries q
        JOIN agents a ON a.id = q.buyer_agent_id
        WHERE a.wallet_address = $1
          AND q.created_at > NOW() - INTERVAL '7 days'
        """,
        wallet_address.lower()
    )
    
    for row in recent_queries:
        if row["question_embedding"] is None:
            continue
        
        # Parse stored embedding (comes as string from pgvector)
        stored_str = row["question_embedding"]
        if isinstance(stored_str, str):
            # Parse vector string [x,y,z] -> list
            stored_str = stored_str.strip('[]')
            stored_embedding = [float(x) for x in stored_str.split(',')]
        else:
            stored_embedding = list(stored_str)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(question_embedding, stored_embedding)
        
        if similarity > 0.85:
            return True
    
    return False

def cosine_similarity(a: list, b: list) -> float:
    """Calculate cosine similarity between two vectors"""
    import math
    
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)

def watermark_answer(answer: str, buyer_id: str) -> str:
    """
    Embed invisible watermark in answer by adding metadata comment.
    This allows tracing leaked answers back to the buyer.
    """
    # Create a subtle hash-based watermark
    watermark = hashlib.sha256(f"{buyer_id}:{answer[:50]}".encode()).hexdigest()[:8]
    
    # Add as HTML comment (invisible to readers, detectable if copied)
    watermarked = f"{answer}\n<!-- acp:{watermark} -->"
    
    return watermarked

async def verify_watermark(answer: str, expected_buyer_id: str) -> bool:
    """
    Verify that an answer contains the correct watermark for a buyer.
    Used for detecting unauthorized redistribution.
    """
    # Extract watermark from answer
    import re
    match = re.search(r'<!-- acp:([a-f0-9]{8}) -->', answer)
    
    if not match:
        return False
    
    found_watermark = match.group(1)
    expected_watermark = hashlib.sha256(f"{expected_buyer_id}:{answer[:50]}".encode()).hexdigest()[:8]
    
    return found_watermark == expected_watermark
