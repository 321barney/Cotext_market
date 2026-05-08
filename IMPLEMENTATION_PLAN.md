# Context Market v2 — Implementation Plan

## Issues & Fixes

### CRITICAL (Blocking Launch)

| # | Issue | File(s) | Fix | Status |
|---|-------|---------|-----|--------|
| 1 | **ESCROW_CONTRACT_ADDRESS placeholder** | `.env`, `config.py` | Add graceful fallback | ✅ Config handles missing contract gracefully |
| 2 | **OPENAI_API_KEY missing** | `synthesis.py` | Update to OpenAI SDK v1+ syntax + add Anthropic fallback | ✅ Fixed |
| 3 | **DB schema mismatch: `query_ratings` vs `ratings`** | `main.py` | Change `query_ratings` → `ratings` (table exists in migration) | ✅ Fixed |
| 4 | **`refunded` mapping missing from contract** | `ContextMarketEscrow.sol`, `payments.py` | Add `refunded` mapping to contract, update ABI | ✅ Fixed |
| 5 | **`seller_reputation` is a VIEW** | `reputation.py`, migration | Convert VIEW → real table + auto-refresh trigger | ✅ Fixed |
| 6 | **Deprecated OpenAI SDK call** | `synthesis.py` | Replace `openai.ChatCompletion.acreate` with `AsyncOpenAI` client | ✅ Fixed |
| 7 | **Watermark logic inverted** | `theft_protection.py`, `main.py` | Pass `buyer_id` instead of `seller_id` to `watermark_answer` | ✅ Fixed |
| 8 | **skill.md stale (x402 vs escrow)** | `skill.md` | Rewrite to describe escrow 2-step flow | ✅ Fixed |
| 9 | **`stateMutability: "nonpayary"` typo** | `payments.py` | Fix to `"nonpayable"` | ✅ Fixed |
| 10 | **Hardcoded log paths** | `scheduler.py`, `payments.py` | Use ENV-configurable paths via `LOG_DIR` | ✅ Fixed |
| 11 | **`.env.example` missing ANTHROPIC_API_KEY** | `.env.example` | Add Claude API key placeholder | ✅ Fixed |

---

## Execution Order

### Phase 1: Contract & DB (Foundation) ✅
- [x] Fix Solidity contract (add `refunded` mapping + check in refund())
- [x] Fix migration (seller_reputation as table + trigger, not view)
- [x] Fix DB naming mismatch (`query_ratings` → `ratings`)

### Phase 2: Backend Code ✅
- [x] Fix `synthesis.py` (OpenAI v1+ AsyncOpenAI + Anthropic fallback)
- [x] Fix `payments.py` (typo, log paths, ABI sync)
- [x] Fix `theft_protection.py` (watermark buyer_id — actually correct, caller was wrong)
- [x] Fix `main.py` (watermark call passes buyer_id + query_ratings → ratings)
- [x] `reputation.py` — already correct, works with new table

### Phase 3: Config & Docs ✅
- [x] Fix `.env.example` (add ANTHROPIC_API_KEY)
- [x] Rewrite `skill.md` for escrow flow
- [x] Fix `scheduler.py` log paths

### Phase 4: Testing ⏳
- [ ] Run `test_escrow.py` against updated contract
- [ ] Test DB schema alignment
- [ ] End-to-end query flow test

---

## Status

**Phase 1-3 COMPLETE** — 2026-04-22  
**Phase 4 PENDING** — requires deployed contract + running DB
