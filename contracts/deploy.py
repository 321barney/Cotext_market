#!/usr/bin/env python3
"""
Context Market Escrow Contract Deployment
Deploys ContextMarketEscrow to Base mainnet or testnet.
"""

import os
import json
from pathlib import Path
from decimal import Decimal

def compile_contract():
    """Compile Solidity contract and return ABI + bytecode."""
    from solcx import compile_source
    
    contract_path = Path(__file__).parent / "ContextMarketEscrow.sol"
    
    with open(contract_path, 'r') as f:
        source = f.read()
    
    compiled = compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version="0.8.20"
    )
    
    # Get the contract (key format: '<filename>:<contract_name>')
    contract_key = "ContextMarketEscrow.sol:ContextMarketEscrow"
    contract_interface = compiled[contract_key]
    
    return contract_interface["abi"], contract_interface["bin"]

def deploy_to_base(
    usdc_address: str,
    platform_wallet: str,
    private_key: str,
    testnet: bool = False
):
    """Deploy escrow contract to Base."""
    from web3 import Web3
    
    # RPC endpoint
    rpc_url = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org") if testnet else os.getenv("BASE_RPC", "https://mainnet.base.org")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Base RPC: {rpc_url}")
    
    # Compile
    abi, bytecode = compile_contract()
    
    # Build contract
    Escrow = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Build transaction
    construct_txn = Escrow.constructor(
        w3.to_checksum_address(usdc_address),
        w3.to_checksum_address(platform_wallet)
    ).build_transaction({
        'from': w3.eth.account.from_key(private_key).address,
        'nonce': w3.eth.get_transaction_count(w3.eth.account.from_key(private_key).address),
        'gas': 1500000,
        'gasPrice': w3.to_wei('0.1', 'gwei'),
        'chainId': 84532 if testnet else 8453
    })
    
    # Sign and send
    signed = w3.eth.account.sign_transaction(construct_txn, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    
    print(f"Deploy transaction sent: {tx_hash.hex()}")
    print("Waiting for confirmation...")
    
    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt.status != 1:
        raise RuntimeError("Deployment failed")
    
    contract_address = receipt.contractAddress
    
    # Save deployment info
    deployed = {
        "network": "base_sepolia" if testnet else "base_mainnet",
        "contract_address": contract_address,
        "usdc_address": usdc_address,
        "platform_wallet": platform_wallet,
        "tx_hash": tx_hash.hex(),
        "block_number": receipt.blockNumber,
        "abi": abi
    }
    
    deployed_path = Path(__file__).parent / "deployed.json"
    with open(deployed_path, 'w') as f:
        json.dump(deployed, f, indent=2)
    
    print(f"\n=== DEPLOYMENT SUCCESSFUL ===")
    print(f"Contract address: {contract_address}")
    print(f"Network: {deployed['network']}")
    print(f"TX hash: {tx_hash.hex()}")
    print(f"Block: {receipt.blockNumber}")
    print(f"Saved to: {deployed_path}")
    print(f"\nBasescan URL:")
    if testnet:
        print(f"  https://sepolia.basescan.org/address/{contract_address}")
    else:
        print(f"  https://basescan.org/address/{contract_address}")
    
    return contract_address, abi

def verify_on_basescan(contract_address: str, api_key: str, testnet: bool = False):
    """Verify contract on Basescan (optional)."""
    import requests
    
    base_url = "https://api-sepolia.basescan.org/api" if testnet else "https://api.basescan.org/api"
    
    # Read source
    contract_path = Path(__file__).parent / "ContextMarketEscrow.sol"
    with open(contract_path, 'r') as f:
        source = f.read()
    
    payload = {
        "apikey": api_key,
        "module": "contract",
        "action": "verifysourcecode",
        "contractaddress": contract_address,
        "sourceCode": source,
        "codeformat": "solidity-single-file",
        "contractname": "ContextMarketEscrow",
        "compilerversion": "v0.8.20",
        "optimizationUsed": "0",
        "runs": "200",
        "evmversion": "paris",
        "licenseType": "1"  # MIT
    }
    
    response = requests.post(base_url, data=payload)
    result = response.json()
    
    if result.get("status") == "1":
        print(f"Verification submitted. GUID: {result.get('result')}")
    else:
        print(f"Verification failed: {result}")
    
    return result

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy Context Market Escrow')
    parser.add_argument('--testnet', action='store_true', help='Deploy to Base Sepolia')
    parser.add_argument('--verify', action='store_true', help='Verify on Basescan after deploy')
    parser.add_argument('--api-key', help='Basescan API key for verification')
    
    args = parser.parse_args()
    
    # Read config from env
    usdc = os.getenv("USDC_CONTRACT", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
    platform = os.getenv("PLATFORM_WALLET")
    private_key = os.getenv("ESCROW_PRIVATE_KEY")
    
    if not platform:
        print("Error: Set PLATFORM_WALLET env variable")
        exit(1)
    
    if not private_key:
        print("Error: Set ESCROW_PRIVATE_KEY env variable")
        exit(1)
    
    print(f"Deploying to {'Base Sepolia' if args.testnet else 'Base Mainnet'}...")
    print(f"USDC: {usdc}")
    print(f"Platform: {platform}")
    print(f"Deployer: {Web3().eth.account.from_key(private_key).address}")
    
    from web3 import Web3
    address, abi = deploy_to_base(usdc, platform, private_key, args.testnet)
    
    if args.verify and args.api_key:
        verify_on_basescan(address, args.api_key, args.testnet)
    
    print(f"\n=== ADD TO .env ===")
    print(f"ESCROW_CONTRACT_ADDRESS={address}")

if __name__ == "__main__":
    main()
