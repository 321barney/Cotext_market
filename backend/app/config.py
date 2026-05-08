from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/contextmarket"
    
    # Base / Escrow
    base_rpc: str = "https://mainnet.base.org"
    base_sepolia_rpc: str = "https://sepolia.base.org"
    escrow_contract_address: Optional[str] = None
    platform_wallet: Optional[str] = None
    escrow_private_key: Optional[str] = None
    
    # App
    app_name: str = "Context Market"
    debug: bool = False
    
    # Query limits
    max_queries_per_day_per_buyer: int = 20
    
    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
