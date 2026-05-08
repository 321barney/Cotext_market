# Context Market v2 — Security Audit & Fixes

## Status: ✅ ALL FIXES COMPLETE

| # | Severity | Issue | Status | Fix |
|---|----------|-------|--------|-----|
| 1 | 🔴 Critical | Dispute — no auth, anyone resolves | ✅ FIXED | Seller-only + admin auth |
| 2 | 🔴 Critical | Race condition payment→delivery | ✅ FIXED | Atomic status `UPDATE ... WHERE status='payment_required'` |
| 3 | 🔴 Critical | No rate limit on registration | ✅ FIXED | IP-based: 5/hour |
| 4 | 🔴 Critical | Refund amount caller-controlled | ✅ FIXED | `amount <= deposits[queryId]` in contract |
| 5 | 🟠 High | Nginx rate limit not applied | ✅ FIXED | `limit_req` zones: 10r/s general, 5r/m query, 5r/h register |
| 6 | 🟠 High | Buyer can query own listing | ✅ FIXED | 400 "Cannot query your own listing" |
| 7 | 🟠 High | Watermark keyed to seller | ✅ FIXED | Now keyed to `buyer_id` |
| 8 | 🟠 High | Private key global + DEBUG=true | ✅ FIXED | Lazy load + startup warning |
| 9 | 🟠 High | /docs publicly accessible | ✅ FIXED | Disabled when `DEBUG=false` |
| 10 | 🟡 Medium | Raw knowledge not persisted | ✅ FIXED | `raw_knowledge_text` column in listings |
| 11 | 🟡 Medium | Fingerprint bypass via multi-agent | ✅ FIXED | Fingerprint keys on `wallet_address` |
| 12 | 🟡 Medium | uuid.UUID() unguarded | ✅ FIXED | `_parse_uuid()` helper → 400 on invalid |
| 13 | 🟡 Medium | Private key printed to stdout | ✅ FIXED | No print statements in payments.py |
| 14 | 🟡 Medium | Wallet not validated at listing | ✅ FIXED | Block store_memory if no wallet |
| 15 | 🟢 Low | Wallet addresses in plain logs | ✅ FIXED | Masked: `0x1234...5678` |
| 16 | 🟢 Low | No CORS policy | ✅ FIXED | `ALLOWED_ORIGINS` env var + middleware |
| 17 | 🟢 Low | Fee not event-logged | ✅ FIXED | `FeeUpdated` event + `setPlatformFee()` |

---

## Fix Details

### #1 — Dispute Authorization
**Before:** `resolve_dispute` had no auth check — any authenticated agent could resolve any dispute.
**After:** Only the seller of the disputed query's listing can resolve. Returns 403 otherwise. Also validates `resolution` param is only `refund` or `release`.

### #2 — Race Condition
**Before:** Two concurrent requests with same `X-Query-ID` could both pass `receive_payment()`, then both call `_process_and_deliver()`, resulting in double-delivery and double-answer.
**After:** Uses atomic `UPDATE queries SET status = 'processing' WHERE status = 'payment_required'`. Second request gets 409 Conflict. Also updates query status to `processing` before calling `_process_and_deliver`.

### #3 — Registration Rate Limit
**Before:** No limit on `/agent/register` — could create unlimited agents to bypass per-buyer fingerprinting.
**After:** IP-based rate limit: 5 registrations per hour per IP. Returns 429 with `Retry-After` header. Also enforced by nginx `limit_req zone=register`.

### #5 — Nginx Rate Limiting
**Before:** Declared in nginx config but no `limit_req` or `limit_req_zone` directives.
**After:** Three zones:
- `api`: 10r/s burst 20 (general API)
- `query`: 5r/m burst 3 (query endpoint — expensive)
- `register`: 5r/h burst 2 (registration — abuse vector)

### #6 — Self-Query Prevention
**Before:** Buyer could query their own listing, effectively paying themselves.
**After:** Returns 400 with "Cannot query your own listing" if `buyer_id == seller_id`.

### #8 — Private Key + DEBUG
**Before:** `ESCROW_PRIVATE_KEY` loaded at module import time (global scope). `DEBUG=true` exposes stack traces with sensitive data.
**After:** Lazy-loaded via `_get_platform_account()` — only called when needed. `DEBUG` defaults to false. Added startup warning: "⚠️ DEBUG=true — Stack traces will expose sensitive data."

### #9 — /docs Access Control
**Before:** FastAPI `/docs` and `/redoc` always public.
**After:** Disabled when `DEBUG=false` via `docs_url=None, redoc_url=None` in FastAPI constructor.

### #10 — Raw Knowledge Persistence
**Before:** `knowledge_text` was chunked immediately; original text lost. Dispute resolver couldn't see what seller actually promised.
**After:** `memory_listings` now has `raw_knowledge_text` column. Stored alongside chunks during `store_memory`.

### #11 — Fingerprint Bypass
**Before:** Query fingerprinting was per `agent_id` — register 100 agents, get 100 query budgets.
**After:** Fingerprinting uses `wallet_address` as the key. Same wallet = same fingerprint, regardless of agent count. SQL joins `agents` table to lookup wallet.

### #12 — UUID Validation
**Before:** `uuid.UUID(req.query_id)` throws unhandled `ValueError` on invalid UUID → 500 Internal Server Error.
**After:** `_parse_uuid()` helper wraps all UUID conversions. Returns 400 with "Invalid X format".

### #13 — Private Key Leakage
**Before:** Potential for private key to be printed in exception handlers or debug output.
**After:** `payments.py` has zero `print()` statements. `_get_escrow_private_key()` returns the key but never logs it. `_mask_wallet()` masks all wallet addresses in logs.

### #14 — Wallet Validation
**Before:** `store_memory` allowed listing creation without wallet → queries would fail at payment time.
**After:** Returns 400 with "Set wallet before creating listings. POST /agent/wallet first." if `wallet_address` is null.

### #15 — Wallet Address Masking
**Before:** Full wallet addresses logged in settlement logs: `seller=0xabc123def456...`
**After:** Masked format: `0x1234...5678` in all logs. `_mask_wallet()` applied in `_log_settlement()`.

### #16 — CORS Policy
**Before:** No CORS headers — frontend on different domain would be blocked.
**After:** `ALLOWED_ORIGINS` env var (comma-separated). Defaults to `APP_URL`. `CORSMiddleware` added with configurable origins.

### #17 — Fee Event Logging
**Before:** `platformFeeBps` set in constructor with no event or setter.
**After:** Added `FeeUpdated(uint256 oldFeeBps, uint256 newFeeBps)` event. Added `setPlatformFee(uint256)` function with max 30% cap.

---

## Verification Checklist

Before deploying to production, verify:

```bash
# 1. DEBUG is false
curl http://localhost:8000/health | grep debug  # should be false

# 2. /docs is not accessible in prod
curl -I http://localhost:8000/docs  # should return 404

# 3. Rate limits work
curl -X POST http://localhost:8000/agent/register  # 6th time should 429

# 4. Self-query blocked
curl -X POST http://localhost:8000/memory/query -H "X-API-Key: YOUR_KEY" \
  -d '{"listing_id": "YOUR_OWN_LISTING", "question": "test"}'  # should 400

# 5. Wallet validation
# Try store_memory without wallet → should 400

# 6. Dispute auth
# Try resolve_dispute as buyer (not seller) → should 403
```

---

*Last updated: 2026-04-22*
*All 17 issues resolved.*
