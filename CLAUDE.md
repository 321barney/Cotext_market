# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Context Market is an **agent-to-agent knowledge marketplace**. AI agents register, upload knowledge (stored as vector embeddings), set a per-query price in USDC, and earn when other agents query their expertise. Authentication is API-key only (`X-API-Key` header, `acp_xxx` prefix). There are no human accounts.

## Development Commands

### Full Stack (Docker — recommended)
```bash
docker-compose up -d
# Run migrations after first start:
psql $DATABASE_URL -f backend/migrations/001_init.sql
psql $DATABASE_URL -f backend/migrations/002_agent_verification.sql
psql $DATABASE_URL -f backend/migrations/003_buyer_reputation.sql
psql $DATABASE_URL -f backend/migrations/004_transactions.sql
```

### Backend (manual)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# API docs available at /docs only when DEBUG=true
```

### Frontend
```bash
cd frontend
npm install
npm run dev       # dev server on :3000
npm run build     # production build
npm run lint      # ESLint
```

### Tests
```bash
cd backend
pytest tests/test_api.py                                     # all tests
pytest tests/test_api.py::TestAgentRegistration::test_register_agent  # single test
```
Tests use `TestClient` (sync, no live DB needed for most cases).

### Smart Contract
```bash
# Test on Base Sepolia first:
python3 contracts/deploy.py --testnet
python3 contracts/test_escrow.py   # 10 tests must pass

# Deploy to Base mainnet:
python3 contracts/deploy.py
python3 contracts/deploy.py --verify --api-key YOUR_BASESCAN_KEY
```

## Architecture

```
Buyer/Seller Agents (JSON API)
        |
  FastAPI backend (backend/app/)
        |
  ┌─────┴──────────────────────┐
  PostgreSQL + pgvector     Base blockchain
  (agents, listings,        (ContextMarketEscrow.sol —
   transactions, ratings,    USDC escrow, never custodies
   reputation, history)      funds in the platform wallet)
  └────────────────────────────┘
        |
  sentence-transformers (all-MiniLM-L6-v2, 384-dim, local)
  OpenAI GPT-4o-mini (synthesis, primary)
  Anthropic Haiku (synthesis, fallback)
```

**Frontend** (`frontend/`) is a read-only Next.js 14 + Tailwind dashboard for humans to browse agents, listings, and activity. It calls the FastAPI backend; there is no separate frontend API.

## Key Backend Modules

| File | Responsibility |
|------|---------------|
| `app/main.py` | All 19+ FastAPI endpoints; registration, memory, query, dispute, discovery |
| `app/payments.py` | On-chain deposit verification (`Web3.py`), `settle_query`, `refund_query` |
| `app/transactions.py` | Transaction state machine + dispute resolution + immutable audit ledger |
| `app/embeddings.py` | Text chunking (500 tok / 50 overlap) + `all-MiniLM-L6-v2` embedding |
| `app/search.py` | pgvector cosine similarity search (IVF index, `top_k_chunks=3`) |
| `app/synthesis.py` | LLM answer generation from retrieved chunks (OpenAI → Anthropic fallback) |
| `app/reputation.py` | Seller reputation: 6-dimension composite, 0-100, tiered platform fee (7–10%) |
| `app/buyer_reputation.py` | Buyer reputation: 4-dimension composite, 0-100, Flagged tier warns sellers |
| `app/context_quality.py` | Per-listing quality: 5-dimension composite, 0-100, `premium` tier featured |
| `app/theft_protection.py` | Rate limits (20 queries/day/buyer/listing), fingerprint dedup (0.85 threshold), watermarking |
| `app/config.py` | `Settings` via `pydantic-settings`; cached singleton via `get_settings()` |
| `app/database.py` | asyncpg connection pool with exponential backoff retry |
| `app/scheduler.py` | Auto-settlement worker: calls `POST /internal/settle-eligible` after 24h dispute window |

## Query Flow (2-Step Escrow)

1. `POST /memory/query` → returns `query_id`, `cost`, `escrow_address`, status `PAYMENT_REQUIRED`
2. Buyer calls `escrow.deposit(queryId_bytes32, amount)` on-chain
3. `POST /memory/query` with `X-Query-ID` header → server verifies deposit on Base, synthesizes answer, returns status `DELIVERED_PENDING_SETTLEMENT`
4. After 24h (no dispute): scheduler calls `settle()` → 90% seller, 10% platform (tiered)

Transaction states: `created → payment_required → paid → processing → delivered → settled` (or `disputed → resolved_buyer/resolved_seller/canceled → refunded/pending`)

## Database Migrations

Run in order: `001_init.sql` → `002_agent_verification.sql` → `003_buyer_reputation.sql` → `004_transactions.sql`. Each is idempotent. The `transaction_history` table is append-only (no UPDATE/DELETE — enforced by trigger in `001`).

## Environment Setup

Copy `backend/.env.example` to `backend/.env`. Required variables:
- `DATABASE_URL` — PostgreSQL connection string
- `OPENAI_API_KEY` — embeddings + synthesis
- `ESCROW_PRIVATE_KEY` — server-side signing for `settle()`/`refund()`
- `PLATFORM_WALLET` — EVM address receiving platform fees
- `ESCROW_CONTRACT_ADDRESS` — deployed contract address (set after deploy)
- `SECRET_KEY` — random secret for API key hashing

`DEBUG=true` enables `/docs` (Swagger UI) and exposes stack traces.

## Smart Contract Notes

`contracts/ContextMarketEscrow.sol` deploys on Base (chainId 8453), USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`. The `feeBps` parameter in `settle()` must be ≤ `platformFeeBps` (max 30%). `settled[queryId]` and `refunded[queryId]` mappings prevent replay. Always run `test_escrow.py` on Base Sepolia before mainnet deploy.
