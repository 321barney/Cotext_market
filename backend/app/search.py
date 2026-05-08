"""
Semantic search over pgvector
"""
from app.database import db
from app.embeddings import embed_text

async def search_knowledge(listing_id: str, question: str, top_k: int = 3):
    """Find top-k relevant chunks for a question using cosine similarity"""
    # Embed the question
    question_embedding = await embed_text(question)
    
    # Search pgvector - returns top-k most similar chunks
    embedding_str = '[' + ','.join(str(x) for x in question_embedding) + ']'
    rows = await db.fetch(
        """
        SELECT chunk_text, chunk_index,
               1 - (embedding <=> $1::vector) as similarity
        FROM memory_chunks
        WHERE listing_id = $2
        ORDER BY embedding <=> $1::vector
        LIMIT $3
        """,
        embedding_str, listing_id, top_k
    )
    
    return [
        {
            "text": row["chunk_text"],
            "index": row["chunk_index"],
            "similarity": row["similarity"]
        }
        for row in rows
    ]
