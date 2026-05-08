#!/usr/bin/env python3
"""
Context Market — Wallet Tools
Read-only utilities for wallet management.
NEVER stores private keys.
"""

import os
import sys
import json
import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any

# USDC on Base
USDC_CONTRACT_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_RPC_URL = "https://mainnet.base.org"
BASE_SEPOLIA_RPC_URL = "https://sepolia.base.org"

# Minimal ERC20 ABI (just balanceOf)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

def get_usdc_balance(address: str, testnet: bool = False) -> Optional[Decimal]:
    """
    Check USDC balance on Base.
    Read-only, no private key needed.
    """
    try:
        from web3 import Web3
        
        rpc_url = BASE_SEPOLIA_RPC_URL if testnet else BASE_RPC_URL
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if not w3.is_connected():
            print(f"Error: Cannot connect to Base RPC ({rpc_url})")
            return None
        
        # Check if address is valid
        if not w3.is_address(address):
            print(f"Error: Invalid address {address}")
            return None
        
        address = w3.to_checksum_address(address)
        
        # Create contract instance
        usdc = w3.eth.contract(
            address=w3.to_checksum_address(USDC_CONTRACT_BASE),
            abi=ERC20_ABI
        )
        
        # Get decimals
        decimals = usdc.functions.decimals().call()
        
        # Get balance
        balance_raw = usdc.functions.balanceOf(address).call()
        balance = Decimal(balance_raw) / Decimal(10 ** decimals)
        
        return balance
        
    except Exception as e:
        print(f"Error checking balance: {e}")
        return None

def get_eth_balance(address: str, testnet: bool = False) -> Optional[Decimal]:
    """
    Check native ETH balance on Base.
    Read-only, no private key needed.
    """
    try:
        from web3 import Web3
        
        rpc_url = BASE_SEPOLIA_RPC_URL if testnet else BASE_RPC_URL
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if not w3.is_connected():
            return None
        
        address = w3.to_checksum_address(address)
        balance_wei = w3.eth.get_balance(address)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        return Decimal(str(balance_eth))
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_wallet() -> Dict[str, str]:
    """
    Generate a new EVM wallet.
    Returns address and private key.
    USER must securely store the private key.
    """
    from eth_account import Account
    import secrets
    
    acct = Account.create(secrets.token_hex(32))
    
    return {
        "address": acct.address,
        "private_key": acct.key.hex(),
        "warning": "STORE PRIVATE KEY SECURELY. NEVER SHARE IT."
    }

def verify_address(address: str) -> bool:
    """Verify if string is a valid EVM address."""
    try:
        from web3 import Web3
        return Web3.is_address(address)
    except:
        return False

def main():
    """CLI interface for wallet tools."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Context Market Wallet Tools')
    parser.add_argument('command', choices=['balance', 'generate', 'verify'])
    parser.add_argument('--address', help='Wallet address')
    parser.add_argument('--testnet', action='store_true', help='Use Base Sepolia testnet')
    
    args = parser.parse_args()
    
    if args.command == 'generate':
        wallet = generate_wallet()
        print("\n=== NEW WALLET GENERATED ===")
        print(f"Address: {wallet['address']}")
        print(f"\n⚠️  {wallet['warning']}")
        print("\nSave this to a secure location (password manager, hardware wallet):")
        print(f"Private Key: {wallet['private_key']}")
        print("\nGive me ONLY the address. Never the private key.")
        
    elif args.command == 'balance':
        if not args.address:
            print("Error: --address required")
            sys.exit(1)
        
        network = "Base Sepolia" if args.testnet else "Base Mainnet"
        print(f"\nChecking balances on {network}...")
        
        usdc = get_usdc_balance(args.address, args.testnet)
        eth = get_eth_balance(args.address, args.testnet)
        
        print(f"\nAddress: {args.address}")
        print(f"USDC: {usdc} {'USDC' if usdc is not None else '(error)'}")
        print(f"ETH: {eth} {'ETH' if eth is not None else '(error)'}")
        
    elif args.command == 'verify':
        if not args.address:
            print("Error: --address required")
            sys.exit(1)
        
        valid = verify_address(args.address)
        print(f"Address {args.address}: {'VALID' if valid else 'INVALID'}")

if __name__ == '__main__':
    main()
