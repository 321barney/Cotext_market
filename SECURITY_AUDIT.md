# Security Audit — Context Market

**Date:** 2026-06-01
**Scope:** Backend API (FastAPI), Next.js frontend + proxy, escrow smart contract, deployment/secrets
**Branch/commit reviewed:** `main` @ `2c63d15`
**Live target:** https://cotrader.cc (frontend) → Railway backend via `/api/proxy`

> ⚠️ **This audit supersedes the previous version of this file.** The prior `SECURITY_AUDIT.md` declared "✅ ALL FIXES COMPLETE" for 17 issues. **Several of those claims do not hold in the current code** — most critically, issue #1 (dispute authorization) is marked "FIXED — Seller-only + admin auth" but the current `resolve_dispute_endpoint` has **no authorization check at all** (see C-1). Treat the old checklist as aspirational, not verified. A broader correctness/architecture review lives in `AUDIT.md`.

---

## 1. Executive Summary

Context Market moves real money (USDC on Base) through a server-signed escrow, so **authorization on money-moving endpoints** and **custody of the escrow signing key** are the highest-stakes areas. This review found one **critical broken-access-control flaw** that can redirect or release escrowed funds, plus high/medium issues around admin authentication, a self-grantable "verified" badge, the proxy's effect on rate limiting, and secret hygiene.

The fundamentals are mostly sound: SQL is uniformly parameterized, API keys are high-entropy and stored hashed, the contract follows checks-effects-interactions, and prompt-injection filtering exists. The main theme is **authorization**, not injection.

### Risk Summary

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| C-1 | 🔴 Critical | Dispute resolution has no authorization — any agent can release/refund any escrow | Open (prev. claimed fixed) |
| H-1 | 🟠 High | Admin key passed as URL query parameter (logged everywhere) | Open |
| H-2 | 🟠 High | Self-grantable "verified agent" badge | Open |
| H-3 | 🟠 High | Escrow signing key is a single hot key with full settle/refund power | By design — needs controls |
| M-1 | 🟡 Medium | Proxy strips client IP → registration rate-limit broken & shared | Open (regression from proxy) |
| M-2 | 🟡 Medium | `backend/.env` tracked in git | Open |
| M-3 | 🟡 Medium | Deposit not bound to buyer identity in `receive_payment` | Open |
| M-4 | 🟡 Medium | Raw exception strings returned to clients (info disclosure) | Open |
| M-5 | 🟡 Medium | CORS `allow_credentials=True` with operator-supplied origins | Config-dependent |
| L-1 | 🟢 Low | Non-constant-time admin key comparison | Open |
| L-2 | 🟢 Low | No contract reentrancy guard (mitigated by CEI) | Open |
| L-3 | 🟢 Low | Answer watermark trivially removable | Informational |
| L-4 | 🟢 Low | Proxy is an unauthenticated, unthrottled relay to the backend | Open |
| I-1 | ⚪ Info | `DEBUG=true` exposes stack traces & docs | Controlled (default off) |
| I-2 | ⚪ Info | No security headers on backend responses | Open |

---

## 2. Methodology & Scope

- Manual source review of `backend/app/*.py`, `contracts/ContextMarketEscrow.sol`, `frontend/app/api/proxy`, and deployment files (`Dockerfile`, `entrypoint.sh`, `migrate.py`, `railway.json`).
- Secret-scanning of tracked files and git history.
- Auth/authorization tracing on every state-changing and money-moving endpoint.
- SQLi, SSRF, path-traversal, CORS, and information-disclosure checks.
- **Not performed:** live dynamic pentest, on-chain fuzzing, dependency CVE scan — recommended as follow-ups.

---

## 3. Critical Findings

### 🔴 C-1 — Dispute resolution has no authorization (money-moving endpoint)

**Location:** `backend/app/main.py` → `resolve_dispute_endpoint` (`POST /query/dispute/resolve`); logic in `backend/app/transactions.py` → `resolve_dispute()`.

**Description:** The endpoint authenticates the caller but performs **no authorization check**. The caller's id is passed only as a label (`resolver_id`) and never checked against the dispute's parties or an admin role:

```python
result = await resolve_dispute_tx(
    dispute_id=dispute_id,
    resolution=resolution,          # attacker chooses
    refund_amount=refund_amount,    # attacker chooses
    resolver_id=str(agent["id"]),   # only a label, never authorized
    notes=notes,
)
```

The old audit claimed this was fixed ("Seller-only + admin auth"); that guard is **absent** in the current code.

**Impact:**
- A **buyer** can open a dispute on a query they already received the answer for, then immediately resolve it `resolved_buyer` with `refund_amount` = the deposit → `resolve_dispute()` calls `refund_query()`, returning the escrowed USDC on-chain. Buyer keeps the answer **and** the money; seller is robbed.
- **Any** agent can resolve **any** dispute (`resolved_seller` / `resolved_buyer` / `canceled`) for any other parties — fund redirection, griefing, settlement manipulation marketplace-wide.

**Likelihood:** High — a single authenticated API call.

**Remediation:**
1. Restrict the endpoint to a platform-admin identity (see H-1 for a real admin model), not any API key.
2. Until an admin model exists, take the public endpoint offline and resolve disputes out-of-band.
3. Server-side cap: reject `refund_amount` greater than the recorded query cost / on-chain deposit (defense in depth — the contract caps it, the server should too).
4. Require the dispute to be `open` and the resolver to be authorized for *that* dispute.

---

## 4. High-Severity Findings

### 🟠 H-1 — Admin key passed as URL query parameter

**Location:** `backend/app/main.py` → `settle_eligible_queries` (`POST /internal/settle-eligible?admin_key=...`).

The settlement endpoint authenticates via `admin_key` in the **query string**, which is captured by web-server/reverse-proxy/Railway/APM logs and browser history. Leakage grants the ability to trigger mass on-chain settlement.

**Remediation:** Move the secret to a header (`X-Admin-Key` / `Authorization: Bearer`), compare in constant time (L-1), and prefer not exposing it over HTTP at all — `scheduler.py` already calls `settle_query()` in-process, so the HTTP endpoint is an extra surface that can be removed or bound to the private network.

### 🟠 H-2 — Self-grantable "verified agent" badge

**Location:** `backend/app/main.py` → `_determine_verification()` (returns `(True, "auto")` for all types) and `verify_agent` (agent can verify itself; `can_verify_any = False  # TODO`).

No real verification challenge exists, yet discovery exposes `verified_only` filtering buyers may trust. Any agent can present as verified.

**Remediation:** Implement a genuine method (wallet-signed challenge or DID proof) before setting `verified_agent = TRUE`; until then label it honestly ("self-attested").

### 🟠 H-3 — Escrow signing key is a single hot key with full power

**Location:** `backend/app/payments.py` (`_get_escrow_private_key`); contract `settle`/`refund`/`emergency*` gated only on `msg.sender == platform`.

One private key in the backend process environment can settle/refund every deposit. Backend compromise = control of the escrow balance.

**Remediation (controls, not redesign):** keep contract balance minimal (settle promptly); store the key in KMS/secret manager or a dedicated signer service rather than a plain env var; add on-chain monitoring/alerting and a spend rate limit; restrict who can read Railway variables; rotate if ever shared.

---

## 5. Medium-Severity Findings

### 🟡 M-1 — Proxy strips client IP; registration rate-limit broken

**Location:** `frontend/app/api/proxy/[...path]/route.ts`; `backend/app/main.py` `_check_registration_rate_limit` (keys on `request.client.host`).

All traffic flows browser → Next.js proxy → backend, and the proxy does not forward `X-Forwarded-For`. The backend therefore sees the **frontend container's IP** for every request, so the IP-keyed 5/hour registration limit lumps the whole internet into one bucket — both trivially exhausted and useless for per-client throttling. State is also per-process and resets on redeploy.

**Remediation:** forward `X-Forwarded-For` from the proxy; have the backend trust it only behind the known proxy; move rate-limit state to shared storage (Redis); add per-API-key limits.

### 🟡 M-2 — `backend/.env` tracked in git

`.gitignore` lists `.env`, but `backend/.env` was committed earlier and remains tracked. **Current content is placeholder/dev values only** (localhost DB creds, no key) — no live secret leaked today — but it's one careless commit from publishing `ESCROW_PRIVATE_KEY`/`DATABASE_URL`.

**Remediation:** `git rm --cached backend/.env && git commit`; keep only `.env.example`. (History is currently clean.)

### 🟡 M-3 — Deposit not bound to buyer identity

`receive_payment()` checks that a deposit for `queryId` exists and is sufficient, but not **who** funded it (`buyer_wallet` is accepted and ignored). Query IDs are private server-generated UUIDs, limiting exploitability, but a leaked `query_id` could let one party's deposit satisfy another's query.

**Remediation:** verify the on-chain `Deposited` event's `buyer` matches the querying agent's wallet.

### 🟡 M-4 — Raw exception strings returned to clients

`payments.py` returns `f"... error: {str(e)}"` (Web3/RPC text) which surfaces to callers via `HTTPException(detail=...)`, potentially leaking RPC endpoints/internal state. Return generic client messages; log details server-side with a correlation id.

### 🟡 M-5 — CORS `allow_credentials=True` with operator-supplied origins

With the same-origin proxy, browser CORS to the backend is largely moot, but `allow_credentials=True` + a future `ALLOWED_ORIGINS=*` would be unsafe (and browser-rejected). Empty origins currently fail closed. Pin exact origins; since auth uses `X-API-Key` (not cookies), consider `allow_credentials=False`.

---

## 6. Low / Informational

- **L-1** — `admin_key != expected_key` is not constant-time; use `hmac.compare_digest`.
- **L-2** — No `nonReentrant` modifier; mitigated by checks-effects-interactions and non-reentrant USDC. Add as defense-in-depth before supporting non-standard tokens.
- **L-3** — `watermark_answer` appends an HTML comment; trivially removable. Tracing hint, not protection.
- **L-4** — `/api/proxy/*` relays to the backend with no edge auth/throttle. Host is fixed (no arbitrary-host SSRF); worst case is reaching other paths on the same backend. Add edge rate limiting; reject unexpected methods.
- **I-1** — `DEBUG` correctly gates `/docs`, `/redoc`, stack traces; default `false`. Keep it off in Railway.
- **I-2** — Frontend sets `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`; the backend API sets none. Add them on the API too.

---

## 7. Smart Contract (`ContextMarketEscrow.sol`)

**Positive:** correct checks-effects-interactions; `settled`/`refunded` replay guards; `_safeTransfer` for non-compliant ERC-20s; `feeBps ≤ platformFeeBps` (≤30%); the previously-broken 2-arg `settle()` (external `this.settle` self-call) is fixed to an internal `_doSettle`.

**Residual:** all privileged functions trust a single `platform` EOA (H-3); no timelock on `setPlatformFee`, no 2-step ownership transfer; `emergency*` after 30 days bypass settled/refunded checks (acceptable, document it). **No external audit on record — strongly recommend a third-party audit + Sepolia-fork run of all paths before holding meaningful value**, and re-run `test_escrow.py` against the fixed contract (it previously exercised the broken signature).

---

## 8. Things Done Well

- **SQL injection:** fully parameterized, incl. the dynamic-clause builder in `transactions.py`; ILIKE wildcards escaped in discovery.
- **API keys:** 256-bit (`secrets.token_urlsafe(32)`), stored only as SHA-256 hashes — acceptable for high-entropy secrets.
- **Prompt injection:** input sanitization + output leakage redaction; raw chunks no longer leaked on LLM failure (prior issue fixed).
- **Fail-closed DB:** `_require_pool()` returns 503 rather than crashing before the pool is ready.
- **Frontend:** same-origin proxy removes most browser-CORS exposure and adds baseline security headers.

---

## 9. Prioritized Remediation Roadmap

**P0 — before holding any real USDC**
1. **C-1** — authorize `/query/dispute/resolve` (admin-only) + server-side `refund_amount` cap.
2. **H-1** — admin key to a header + constant-time compare, or remove the HTTP settlement endpoint.
3. **H-3** — move `ESCROW_PRIVATE_KEY` to KMS/secret manager; minimize escrow balance; add settle/refund monitoring.
4. Third-party contract audit + Sepolia-fork re-test.

**P1**
5. **H-2** — real verification challenge or relabel the badge.
6. **M-1** — forward `X-Forwarded-For`; shared per-IP + per-key rate limiting.
7. **M-2** — `git rm --cached backend/.env`.
8. **M-3** — bind deposits to the buyer wallet.

**P2 — hardening**
9. **M-4/M-5/L-1/I-2** — generic client errors, tighten CORS, constant-time compares, backend security headers.
10. **L-4** — edge rate limiting / WAF in front of `/api/proxy`.
11. Add dependency CVE scanning (`pip-audit`, `npm audit`) and a live pentest pass.

---

*Severity reflects impact × likelihood for a fund-custodying marketplace. Point-in-time for commit `2c63d15`; re-audit after P0 items land. Where this contradicts the previous "all fixed" checklist, this document reflects the code as actually written.*
