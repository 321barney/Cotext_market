from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/contextmarket"
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_command_timeout: int = 60

    # Base / Escrow
    base_rpc: str = "https://mainnet.base.org"
    base_sepolia_rpc: str = "https://sepolia.base.org"
    escrow_contract_address: Optional[str] = None
    platform_wallet: Optional[str] = None
    escrow_private_key: Optional[str] = None

    # Blockchain
    usdc_contract_address: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    base_chain_id: int = 8453
    gas_limit: int = 200000
    gas_price_gwei: float = 0.1

    # App
    app_name: str = "Context Market"
    app_url: Optional[str] = None
    debug: bool = False

    # Query limits
    max_queries_per_day_per_buyer: int = 20

    # Rate Limits
    registration_limit_per_hour: int = 5

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Dispute
    dispute_window_hours: int = 24
    # Platform auto-resolution rule: refund the buyer if the answer's
    # question→answer semantic relevance is below this threshold.
    dispute_auto_refund_relevance_threshold: float = 0.30

    # Theft Protection
    fingerprint_similarity_threshold: float = 0.85

    # Search
    top_k_chunks: int = 3

    # Payments
    platform_fee_bps: int = 1000  # 10%

    # --- Agent Verification & Type Config ---
    # Allowed agent framework / runtime types
    allowed_agent_types: List[str] = [
        'langchain',
        'crewai',
        'autogen',
        'custom',
        'unknown',
    ]

    # Whether newly registered agents must be verified before publishing
    require_agent_verification: bool = False

    # Supported verification methods
    verification_methods: List[str] = [
        'did',
        'challenge',
        'manual',
    ]

    # Capability taxonomy categories
    capability_categories: List[str] = [
        'domain',
        'skill',
        'tool',
    ]

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
