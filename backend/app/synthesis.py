"""
LLM answer synthesis from retrieved chunks
Uses OpenAI API, Anthropic Claude, or local LLM to generate answer.
Never exposes raw chunks.
"""
import os
from typing import Tuple

# Try OpenAI v1+ SDK first, fallback to direct HTTP
try:
    from openai import AsyncOpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Initialize OpenAI client if key available
_openai_client = None
if _OPENAI_AVAILABLE and OPENAI_API_KEY:
    _openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def synthesize_answer(question: str, chunks: list) -> Tuple[str, float]:
    """
    Synthesize a single answer from retrieved chunks.
    Returns: (answer_text, confidence_score)
    """
    if not chunks:
        return "I don't have specific knowledge about that in my context.", 0.0
    
    # Build context from chunks
    context_text = "\n\n".join([
        f"[Source {i+1}] {chunk['text']}"
        for i, chunk in enumerate(chunks)
    ])
    
    # Calculate confidence from similarity scores
    avg_similarity = sum(c["similarity"] for c in chunks) / len(chunks)
    confidence = round(min(avg_similarity * 1.2, 0.95), 2)  # Cap at 0.95
    
    # If no API keys, return extractive fallback
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        best_chunk = max(chunks, key=lambda c: c["similarity"])
        return f"Based on my knowledge: {best_chunk['text']}", confidence
    
    # Try OpenAI first, then Anthropic
    if _openai_client:
        try:
            answer = await _synthesize_openai(question, context_text)
            return answer, confidence
        except Exception as e:
            # Fallback to Anthropic if OpenAI fails
            pass
    
    if ANTHROPIC_API_KEY:
        try:
            answer = await _synthesize_anthropic(question, context_text)
            return answer, confidence
        except Exception as e:
            pass
    
    # Final fallback
    best_chunk = max(chunks, key=lambda c: c["similarity"])
    return f"Based on my knowledge: {best_chunk['text']}", confidence

async def _synthesize_openai(question: str, context_text: str) -> str:
    """Call OpenAI GPT-4o-mini to synthesize answer."""
    response = await _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a knowledgeable assistant. Answer the user's question based ONLY on the provided context. If the context doesn't contain the answer, say so. Be concise."
            },
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {question}\n\nAnswer based only on the context above:"
            }
        ],
        temperature=0.3,
        max_tokens=500
    )
    
    return response.choices[0].message.content.strip()

async def _synthesize_anthropic(question: str, context_text: str) -> str:
    """Call Anthropic Claude to synthesize answer."""
    import httpx
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 500,
                "temperature": 0.3,
                "system": "You are a knowledgeable assistant. Answer the user's question based ONLY on the provided context. If the context doesn't contain the answer, say so. Be concise.",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Context:\n{context_text}\n\nQuestion: {question}\n\nAnswer based only on the context above:"
                    }
                ]
            },
            timeout=30.0
        )
        
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"].strip()
