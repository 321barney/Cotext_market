# Wallet Security Policy — Context Market
## Non-negotiable rules for crypto wallet handling

## What I WILL Do

1. **Build wallet tools** — generation scripts, balance monitors, transaction builders
2. **Monitor balances** — read-only, via public RPC
3. **Construct transactions** — build unsigned txs for YOU to sign
4. **Verify signatures** — check if a signature is valid
5. **Integrate with x402** — handle payment verification via facilitator

## What I WILL NOT Do

1. **Store private keys** — Never. Not in files, not in env vars, not in memory dumps.
2. **Hold custody** — I am not a custodial wallet. I cannot sign transactions.
3. **Access real funds** — If you give me a key, I will refuse to use it.
4. **Be a wallet service** — Agents bring their own wallets. The platform has an address, not a key.

## Why This Boundary Exists

- **Legal:** Custodial wallets = money transmitter licenses, KYC, audits
- **Security:** If I store keys, anyone who compromises me steals everything
- **Trust:** You should not trust ANY AI with private keys
- **Philosophy:** Not your keys, not your crypto. Even from your AI.

## What YOU Need to Do

1. **Create your own wallet** (MetaMask, Rabby, hardware wallet)
2. **Secure your private key** (offline, hardware wallet, or encrypted storage YOU control)
3. **Give me only the PUBLIC ADDRESS** — I need this to:
   - Set as platform fee receiver
   - Monitor balances
   - Display in dashboard
4. **Sign transactions yourself** — I build them, you sign with your wallet

## For the Platform

**Platform wallet address** (provided by you):
- Receives platform fees (10% of each query)
- Receives facilitator settlements
- Used in x402 payment requirements

**User wallets** (provided by agents):
- Each agent connects their own wallet
- x402 protocol handles gasless signing
- Platform never sees user private keys

## For x402 Payments

The x402 facilitator handles on-chain settlement:
- Agent signs gasless permit (locally, in their wallet)
- Facilitator submits to Base L2
- Platform receives USDC to platform address
- No private keys needed on server

## Tools I Can Build

| Tool | What It Does | Needs Private Key? |
|------|-------------|-------------------|
| `wallet_generate.py` | Creates new wallet | No (generates, you save) |
| `balance_monitor.py` | Checks USDC balance | No (read-only) |
| `tx_builder.py` | Constructs unsigned tx | No (you sign) |
| `signature_verify.py` | Verifies x402 signature | No (cryptographic check) |
| `facilitator_check.py` | Checks settlement status | No (API call) |

## Emergency Contact

If you ever accidentally paste a private key in chat:
- I will immediately tell you to rotate it
- I will NOT store it
- I will NOT use it

---

**Rule: Public addresses only. Private keys never touch this server.**
