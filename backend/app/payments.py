"""
Context Market — Escrow Payment System
3 functions only: receive_payment, settle_query, retry_failed_settlement

Escrow contract on Base handles all fund custody.
Platform never holds USDC directly.
"""

import os
import json
import time
from decimal import Decimal
from typing import Optional, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.database import db
from app.config import get_settings

settings = get_settings()

# Contract setup
BASE_RPC = os.getenv("BASE_RPC", "https://mainnet.base.org")

# Lazy-loaded globals (not loaded at import time)
_ESCROW_CONTRACT = None
_PLATFORM_WALLET = None
_ESCROW_PRIVATE_KEY = None

def _get_escrow_contract_addr() -> str:
    addr = os.getenv("ESCROW_CONTRACT_ADDRESS")
    if not addr:
        raise RuntimeError("ESCROW_CONTRACT_ADDRESS not set")
    return addr

def _get_platform_wallet() -> str:
    global _PLATFORM_WALLET
    if _PLATFORM_WALLET is None:
        _PLATFORM_WALLET = os.getenv("PLATFORM_WALLET")
    if not _PLATFORM_WALLET:
        raise RuntimeError("PLATFORM_WALLET not set")
    return _PLATFORM_WALLET

def _get_escrow_private_key() -> str:
    global _ESCROW_PRIVATE_KEY
    if _ESCROW_PRIVATE_KEY is None:
        _ESCROW_PRIVATE_KEY = os.getenv("ESCROW_PRIVATE_KEY")
    if not _ESCROW_PRIVATE_KEY:
        raise RuntimeError("ESCROW_PRIVATE_KEY not set")
    return _ESCROW_PRIVATE_KEY

def _mask_wallet(addr: str) -> str:
    """Mask wallet for logs: 0x1234...5678"""
    if not addr or len(addr) < 10:
        return addr or "unknown"
    return f"{addr[:6]}...{addr[-4:]}"

# Minimal ERC20 ABI (transferFrom event)
USDC_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

ESCROW_ABI = [
    {
        "inputs": [{"name": "_usdc", "type": "address"}, {"name": "_platform", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "queryId", "type": "bytes32"},
            {"indexed": False, "name": "buyer", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"}
        ],
        "name": "Deposited",
        "type": "event"
    },
    {
        "inputs": [{"name": "queryId", "type": "bytes32"}, {"name": "seller", "type": "address"}],
        "name": "settle",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "queryId", "type": "bytes32"}, {"name": "buyer", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "refund",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "queryId", "type": "bytes32"}],
        "name": "deposits",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "queryId", "type": "bytes32"}],
        "name": "settled",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "queryId", "type": "bytes32"}],
        "name": "refunded",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def _get_web3():
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    if not w3.is_connected():
        raise ConnectionError("Cannot connect to Base RPC")
    return w3

def _get_escrow_contract(w3):
    addr = _get_escrow_contract_addr()
    return w3.eth.contract(
        address=w3.to_checksum_address(addr),
        abi=ESCROW_ABI
    )

def _get_platform_account(w3):
    pk = _get_escrow_private_key()
    return w3.eth.account.from_key(pk)

# ======================
# Function 1: Receive Payment
# ======================

async def receive_payment(
    buyer_wallet: str,
    amount_usdc: Decimal,
    query_id: str
) -> Tuple[bool, str]:
    """
    Verify buyer sent USDC to escrow contract.
    
    Checks:
    1. Deposit event exists for query_id
    2. Deposit amount >= required amount
    3. Deposit not already settled or refunded
    
    Returns: (confirmed: bool, message: str)
    """
    try:
        w3 = _get_web3()
        escrow = _get_escrow_contract(w3)
        
        # Convert query_id to bytes32
        query_bytes = w3.to_bytes(hexstr=query_id) if query_id.startswith("0x") else w3.keccak(text=query_id)
        
        # Check deposit amount on-chain
        deposit_raw = escrow.functions.deposits(query_bytes).call()
        deposit_amount = Decimal(deposit_raw) / Decimal(10**6)  # USDC has 6 decimals
        
        if deposit_amount == 0:
            return False, "No deposit found for this query_id"
        
        # Check if deposit meets required amount
        required_amount = Decimal(str(amount_usdc))
        if deposit_amount < required_amount:
            return False, f"Insufficient deposit: {deposit_amount} < {required_amount}"
        
        # Check if already settled or refunded
        is_settled = escrow.functions.settled(query_bytes).call()
        is_refunded = escrow.functions.refunded(query_bytes).call()
        
        if is_settled:
            return False, "Already settled"
        if is_refunded:
            return False, "Already refunded"
        
        return True, f"Deposit confirmed: {deposit_amount} USDC"
        
    except Exception as e:
        return False, f"Verification error: {str(e)}"

# ======================
# Function 2: Settle Query
# ======================

async def settle_query(
    query_id: str,
    seller_wallet: str,
    amount_usdc: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Call escrow contract settle() function.
    Contract automatically splits: 90% to seller, 10% to platform.
    
    Returns: (success: bool, tx_hash: str or error message)
    """
    try:
        w3 = _get_web3()
        escrow = _get_escrow_contract(w3)
        account = _get_platform_account(w3)
        
        # Convert query_id to bytes32
        query_bytes = w3.to_bytes(hexstr=query_id) if query_id.startswith("0x") else w3.keccak(text=query_id)
        
        # Check preconditions
        is_settled = escrow.functions.settled(query_bytes).call()
        if is_settled:
            return False, "Already settled"
        
        is_refunded = escrow.functions.refunded(query_bytes).call()
        if is_refunded:
            return False, "Already refunded"
        
        deposit_raw = escrow.functions.deposits(query_bytes).call()
        if deposit_raw == 0:
            return False, "No deposit found"
        
        # Build settle transaction
        seller_checksum = w3.to_checksum_address(seller_wallet)
        
        settle_txn = escrow.functions.settle(query_bytes, seller_checksum).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': settings.gas_limit,
            'gasPrice': w3.to_wei(str(settings.gas_price_gwei), 'gwei'),
            'chainId': settings.base_chain_id
        })
        
        # Sign and send
        pk = _get_escrow_private_key()
        signed = w3.eth.account.sign_transaction(settle_txn, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status != 1:
            return False, f"Transaction failed: {tx_hash.hex()}"
        
        tx_hash_hex = tx_hash.hex()

        # Log to query table
        await db.execute(
            """
            UPDATE queries
            SET status = 'settled', tx_hash = $1, settled_at = NOW()
            WHERE id = $2
            """,
            tx_hash_hex, query_id
        )

        # Record settlement in transaction_history (immutable audit trail)
        try:
            from app.transactions import record_settlement_transaction
            platform_fee = amount_usdc * Decimal("0.10")  # 10% platform fee
            seller_amount = amount_usdc - platform_fee
            await record_settlement_transaction(
                query_id=query_id,
                amount_usdc=amount_usdc,
                fee_usdc=platform_fee,
                tx_hash=tx_hash_hex
            )
        except Exception as e:
            logger.warning(f"Failed to record settlement transaction: {e}")

        # Log to settlement log (masked wallet)
        _log_settlement(query_id, _mask_wallet(seller_wallet), amount_usdc, tx_hash_hex)

        return True, tx_hash_hex
        
    except Exception as e:
        return False, f"Settlement error: {str(e)}"

# ======================
# Function 3: Retry Failed Settlement
# ======================

async def retry_failed_settlement(query_id: str) -> Tuple[bool, str]:
    """
    Retry settlement for a query that previously failed.
    
    Idempotent: checks if already settled on-chain first.
    After 3 failures, logs to failed_settlements table.
    
    Returns: (success: bool, message: str)
    """
    try:
        w3 = _get_web3()
        escrow = _get_escrow_contract(w3)
        
        # Convert query_id to bytes32
        query_bytes = w3.to_bytes(hexstr=query_id) if query_id.startswith("0x") else w3.keccak(text=query_id)
        
        # Check if already settled (idempotency)
        is_settled = escrow.functions.settled(query_bytes).call()
        if is_settled:
            await db.execute(
                "UPDATE queries SET status = 'settled' WHERE id = $1",
                query_id
            )
            return True, "Already settled on-chain"
        
        is_refunded = escrow.functions.refunded(query_bytes).call()
        if is_refunded:
            await db.execute(
                "UPDATE queries SET status = 'refunded' WHERE id = $1",
                query_id
            )
            return True, "Already refunded on-chain"
        
        # Get query details
        query = await db.fetchrow(
            "SELECT buyer_agent_id, listing_id, cost FROM queries WHERE id = $1",
            query_id
        )
        
        if not query:
            return False, "Query not found"
        
        # Get seller wallet
        listing = await db.fetchrow(
            "SELECT agent_id FROM memory_listings WHERE id = $1",
            query["listing_id"]
        )
        
        if not listing:
            return False, "Listing not found"
        
        seller = await db.fetchrow(
            "SELECT wallet_address FROM agents WHERE id = $1",
            listing["agent_id"]
        )
        
        if not seller or not seller["wallet_address"]:
            return False, "Seller has no wallet"
        
        # Retry settlement
        success, result = await settle_query(
            query_id,
            seller["wallet_address"],
            query["cost"]
        )
        
        if success:
            return True, f"Settlement successful: {result}"
        
        # Check retry count
        retry_count = await db.fetchval(
            "SELECT COALESCE(retry_count, 0) FROM queries WHERE id = $1",
            query_id
        ) or 0
        
        retry_count += 1
        
        if retry_count >= 3:
            # Log to failed_settlements
            await db.execute(
                """
                INSERT INTO failed_settlements (query_id, error, retry_count, created_at)
                VALUES ($1, $2, $3, NOW())
                """,
                query_id, result, retry_count
            )
            
            await db.execute(
                "UPDATE queries SET retry_count = $1, status = 'failed' WHERE id = $2",
                retry_count, query_id
            )
            
            return False, f"Failed after 3 retries. Logged to failed_settlements."
        
        # Increment retry count
        await db.execute(
            "UPDATE queries SET retry_count = $1 WHERE id = $2",
            retry_count, query_id
        )
        
        return False, f"Retry {retry_count}/3 failed: {result}"
        
    except Exception as e:
        return False, f"Retry error: {str(e)}"

# ======================
# Helpers
# ======================

def _log_settlement(query_id: str, seller: str, amount: Decimal, tx_hash: str):
    """Log settlement to daily log file."""
    import logging
    from pathlib import Path
    
    # Use relative log dir or fallback to workspace
    log_base = os.getenv("LOG_DIR", "/root/.openclaw/workspace/innovations/context-market-v2/logs")
    log_dir = Path(log_base) / "settlements"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = log_dir / f"{date_str}.log"
    
    logger = logging.getLogger("settlements")
    # Avoid duplicate handlers
    if not any(isinstance(h, logging.FileHandler) and str(h.baseFilename) == str(log_file.resolve()) for h in logger.handlers):
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
        logger.addHandler(handler)
    
    logger.setLevel(logging.INFO)
    logger.info(f"SETTLED | query_id={query_id} | seller={seller} | amount={amount} | tx={tx_hash}")

# ======================
# Refund Function (for disputes)
# ======================

async def refund_query(query_id: str, buyer_wallet: str) -> Tuple[bool, str]:
    """
    Call escrow contract refund() function.
    Returns all deposited USDC to buyer.
    """
    try:
        w3 = _get_web3()
        escrow = _get_escrow_contract(w3)
        account = _get_platform_account(w3)
        
        query_bytes = w3.to_bytes(hexstr=query_id) if query_id.startswith("0x") else w3.keccak(text=query_id)
        
        # Check preconditions
        is_settled = escrow.functions.settled(query_bytes).call()
        if is_settled:
            return False, "Already settled"
        
        is_refunded = escrow.functions.refunded(query_bytes).call()
        if is_refunded:
            return False, "Already refunded"
        
        # Build refund transaction
        buyer_checksum = w3.to_checksum_address(buyer_wallet)
        
        # Get deposit amount for refund
        deposit_raw = escrow.functions.deposits(query_bytes).call()
        
        refund_txn = escrow.functions.refund(query_bytes, buyer_checksum, deposit_raw).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': settings.gas_limit,
            'gasPrice': w3.to_wei(str(settings.gas_price_gwei), 'gwei'),
            'chainId': settings.base_chain_id
        })
        
        pk = _get_escrow_private_key()
        signed = w3.eth.account.sign_transaction(refund_txn, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status != 1:
            return False, f"Refund transaction failed: {tx_hash.hex()}"
        
        await db.execute(
            """
            UPDATE queries 
            SET status = 'refunded', tx_hash = $1, settled_at = NOW()
            WHERE id = $2
            """,
            tx_hash.hex(), query_id
        )
        
        return True, tx_hash.hex()
        
    except Exception as e:
        return False, f"Refund error: {str(e)}"
