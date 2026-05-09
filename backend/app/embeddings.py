"""
Embedding pipeline using sentence-transformers
"""
import numpy as np
from sentence_transformers import SentenceTransformer
import asyncio
from app.config import get_settings

settings = get_settings()

# Load model once at startup
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list:
    """Split text into overlapping chunks"""
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if overlap is None:
        overlap = settings.chunk_overlap
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = words[i:i + chunk_size]
        chunks.append(' '.join(chunk))
    
    return chunks

async def embed_text(text: str) -> list:
    """Generate embedding vector for text"""
    model = get_model()
    
    # Run in threadpool to not block async event loop
    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None, 
        lambda: model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    )
    
    return embedding.tolist()

async def embed_batch(texts: list) -> list:
    """Generate embeddings for multiple texts"""
    model = get_model()
    
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None,
        lambda: model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    )
    
    return embeddings.tolist()
