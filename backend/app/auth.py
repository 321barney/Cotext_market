import hashlib
import secrets
from fastapi import HTTPException, Header
from app.database import db

API_KEY_PREFIX = "acp_"

def generate_api_key():
    """Generate a random API key"""
    raw_key = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

async def get_agent_from_api_key(api_key: str = Header(..., alias="X-API-Key")):
    """Validate API key and return agent"""
    if not api_key.startswith(API_KEY_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    agent = await db.fetchrow(
        "SELECT id, name, wallet_address, wallet_chain, credit_balance, earnings_balance FROM agents WHERE api_key_hash = $1",
        key_hash
    )
    
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return dict(agent)
