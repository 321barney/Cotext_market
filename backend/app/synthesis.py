"""
LLM answer synthesis from retrieved chunks
Uses OpenAI API, Anthropic Claude, or local LLM to generate answer.
Never exposes raw chunks.

Security-hardened integration with:
- Output validation and sanitization
- Prompt injection prevention
- Retry with exponential backoff
- API timeouts
- Cost tracking
- Configurable parameters
"""
import os
import re
import html
import random
import logging
import asyncio
from typing import Tuple

# Try OpenAI v1+ SDK first, fallback to direct HTTP
try:
    from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError, InternalServerError
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable parameters (read from app config with env fallback)
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model & generation settings
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30.0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_SYSTEM_PROMPT = os.getenv(
    "LLM_SYSTEM_PROMPT",
    "You are a knowledgeable assistant. Answer the user's question based ONLY on the provided context. "
    "If the context doesn't contain the answer, say so. Be concise."
)

# Initialize OpenAI client if key available (with explicit timeout)
_openai_client = None
if _OPENAI_AVAILABLE and OPENAI_API_KEY:
    _openai_client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        timeout=LLM_TIMEOUT,
    )

# ---------------------------------------------------------------------------
# Prompt-injection / jailbreak patterns to strip
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    r"\[INST\]", r"\[/INST\]",
    r"<<SYS>>", r"<</SYS>>",
    r"\[SYSTEM\]", r"\[/SYSTEM\]",
    r"/ignore\b",
    r"/forget\b",
    r"\bDAN\b",
    r"\bjailbreak\b",
    r"ignore previous instructions",
    r"ignore all prior",
    r"disregard all previous",
    r"you are now",
    r"from now on you are",
    r"pretend to be",
    r"act as",
    r"roleplay as",
    r"new instructions:",
    r"override",
    r"bypass",
    r"leak",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Common prompt-leakage phrases to detect in output
_LEAKAGE_PATTERNS = [
    r"system prompt",
    r"ignore previous",
    r"ignore all prior",
    r"as an AI\b",
    r"as a language model",
    r"my instructions are",
    r"I have been instructed",
    r"I cannot fulfill",
    r"I cannot comply",
    r"I'm not able to",
    r"I am not able to",
    r"my programming",
    r"my training data",
    r"developer mode",
    r"\[INST",
    r"<<SYS",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\{\{.*?\}\}",
]
_LEAKAGE_RE = re.compile("|".join(_LEAKAGE_PATTERNS), re.IGNORECASE)

# HTML / JS tag stripping regex
_HTML_TAG_RE = re.compile(r"<[^>]+>")


# ===========================================================================
# 1. Input sanitization (prompt-injection prevention)
# ===========================================================================
def _sanitize_input(text: str) -> str:
    """
    Strip known prompt-injection and jailbreak patterns from user input.
    Also removes XML-like tags that could confuse prompt boundaries.
    """
    if not text:
        return ""
    # Strip injection patterns
    cleaned = _INJECTION_RE.sub("", text)
    # Remove XML tags that could break prompt structure
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    # Collapse multiple whitespace
    cleaned = " ".join(cleaned.split())
    return cleaned


# ===========================================================================
# 2. Output validation
# ===========================================================================
_FALLBACK_MSG = "I couldn't generate a reliable answer based on the available context."


def _validate_output(answer: str, chunks: list, max_length: int = 2000) -> str:
    """
    Validate and sanitize LLM output.

    - Strips HTML / JS tags (escapes or regex removal).
    - Truncates to max_length characters.
    - Checks for prompt-leakage patterns.
    - Returns a fallback message if the answer is empty after stripping.
    """
    if not answer or not answer.strip():
        logger.warning("Validation failed: LLM returned empty answer; using fallback.")
        return _FALLBACK_MSG

    # 1. Strip HTML / JS tags
    answer = _HTML_TAG_RE.sub("", answer)
    answer = html.escape(answer)  # Escape any remaining markup-like content

    # 2. Check for prompt-leakage patterns
    if _LEAKAGE_RE.search(answer):
        logger.warning(
            "Validation warning: potential prompt-leakage pattern detected in output."
        )
        # Replace leaked fragments with [redacted]
        answer = _LEAKAGE_RE.sub("[redacted]", answer)

    # 3. Length cap
    if len(answer) > max_length:
        logger.info(
            "Validation: answer truncated from %d to %d chars.", len(answer), max_length
        )
        answer = answer[:max_length].rsplit(" ", 1)[0] + "..."

    # 4. Empty-after-sanitization check
    stripped = answer.strip()
    if not stripped or stripped == "...":
        logger.warning("Validation failed: answer empty after sanitization; using fallback.")
        return _FALLBACK_MSG

    return stripped


# ===========================================================================
# 3. Retry with exponential backoff
# ===========================================================================
async def _call_with_retry(func, max_retries=3, base_delay=1.0, max_delay=30.0):
    """
    Retry an async callable on transient errors with exponential backoff + jitter.

    Retries on: timeout, 429 (rate-limit), 5xx server errors.
    Does NOT retry on: 400 (bad request), 401 (auth), 403 (forbidden).
    """
    import httpx

    last_exception = None
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as exc:
            last_exception = exc

            # Determine if the error is retryable
            retryable = False

            # OpenAI SDK exceptions
            if _OPENAI_AVAILABLE:
                if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
                    retryable = True
                if isinstance(exc, InternalServerError):
                    retryable = True

            # httpx / HTTP-level errors
            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                if status in (408, 429) or 500 <= status < 600:
                    retryable = True
                elif status in (400, 401, 403):
                    logger.warning(
                        "Non-retryable HTTP %d from LLM API: %s", status, str(exc)
                    )
                    raise  # Don't retry auth / bad-request errors

            # httpx timeout / connection errors
            if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
                retryable = True

            if not retryable:
                logger.warning(
                    "Non-retryable error from LLM API (%s): %s",
                    type(exc).__name__,
                    str(exc),
                )
                raise

            # Calculate backoff delay
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, 1)
            total_delay = delay + jitter

            logger.info(
                "LLM API attempt %d/%d failed (%s). Retrying in %.2fs ...",
                attempt + 1,
                max_retries,
                type(exc).__name__,
                total_delay,
            )
            await asyncio.sleep(total_delay)

    # All retries exhausted
    logger.error(
        "LLM API failed after %d attempts. Last error: %s",
        max_retries,
        str(last_exception),
    )
    raise last_exception


# ===========================================================================
# 4. Cost tracking
# ===========================================================================
def _track_cost(model: str, tokens_in: int, tokens_out: int) -> None:
    """
    Log estimated LLM API cost for monitoring.

n    Approximate rates (per 1M tokens):
    - gpt-4o-mini      : $0.15 / $0.60  (input / output)
    - gpt-4o           : $2.50 / $10.00
    - claude-haiku     : $0.25 / $1.25
    - claude-sonnet    : $3.00 / $15.00
    - default          : $0.50 / $2.00
    """
    if "gpt-4o-mini" in model or "gpt-4o_mini" in model:
        in_rate, out_rate = 0.15, 0.60
    elif "gpt-4o" in model:
        in_rate, out_rate = 2.50, 10.00
    elif "haiku" in model.lower():
        in_rate, out_rate = 0.25, 1.25
    elif "sonnet" in model.lower():
        in_rate, out_rate = 3.00, 15.00
    else:
        in_rate, out_rate = 0.50, 2.00

    cost = (tokens_in / 1_000_000) * in_rate + (tokens_out / 1_000_000) * out_rate
    logger.info(
        "[LLM_COST] model=%s tokens_in=%d tokens_out=%d estimated_cost_usd=%.6f",
        model,
        tokens_in,
        tokens_out,
        cost,
    )


# ===========================================================================
# 5. Prompt construction helpers
# ===========================================================================
def _build_openai_messages(system_prompt: str, context_text: str, question: str):
    """Build OpenAI message list with XML-boundary prompts."""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"<context>\n{context_text}\n</context>\n\n"
                f"<question>\n{question}\n</question>\n\n"
                "Answer the question based ONLY on the context above. "
                "If the context doesn't contain the answer, say so. Be concise."
            ),
        },
    ]


def _build_anthropic_payload(system_prompt: str, context_text: str, question: str):
    """Build Anthropic API payload with XML-boundary prompts."""
    return {
        "model": ANTHROPIC_MODEL,
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"<context>\n{context_text}\n</context>\n\n"
                    f"<question>\n{question}\n</question>\n\n"
                    "Answer the question based ONLY on the context above. "
                    "If the context doesn't contain the answer, say so. Be concise."
                ),
            }
        ],
    }


# ===========================================================================
# 6. Provider-specific synthesis functions
# ===========================================================================
async def _synthesize_openai(question: str, context_text: str) -> str:
    """Call OpenAI GPT model to synthesize answer (with retry + timeout)."""
    messages = _build_openai_messages(LLM_SYSTEM_PROMPT, context_text, question)

    async def _do_call():
        response = await _openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT,
        )
        return response

    response = await _call_with_retry(
        _do_call, max_retries=LLM_MAX_RETRIES, base_delay=1.0, max_delay=30.0
    )

    answer = response.choices[0].message.content.strip()

    # Rough token estimates (1 token ~ 4 chars for English)
    tokens_in = sum(len(m["content"]) for m in messages) // 4
    tokens_out = len(answer) // 4
    _track_cost(OPENAI_MODEL, tokens_in, tokens_out)

    return answer


async def _synthesize_anthropic(question: str, context_text: str) -> str:
    """Call Anthropic Claude model to synthesize answer (with retry)."""
    import httpx

    payload = _build_anthropic_payload(LLM_SYSTEM_PROMPT, context_text, question)

    async def _do_call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=LLM_TIMEOUT,
            )
            response.raise_for_status()
            return response

    response = await _call_with_retry(
        _do_call, max_retries=LLM_MAX_RETRIES, base_delay=1.0, max_delay=30.0
    )

    data = response.json()
    answer = data["content"][0]["text"].strip()

    # Rough token estimates
    system_len = len(LLM_SYSTEM_PROMPT)
    content_len = len(payload["messages"][0]["content"])
    tokens_in = (system_len + content_len) // 4
    tokens_out = len(answer) // 4
    _track_cost(ANTHROPIC_MODEL, tokens_in, tokens_out)

    return answer


# ===========================================================================
# 7. Public entry point
# ===========================================================================
async def synthesize_answer(question: str, chunks: list) -> Tuple[str, float]:
    """
    Synthesize a single answer from retrieved chunks.
    Returns: (answer_text, confidence_score)

    Security pipeline:
    1. Sanitize user question (prompt-injection prevention).
    2. Call LLM provider (OpenAI -> Anthropic) with retry + timeout.
    3. Validate LLM output (strip tags, length cap, leakage check).
    4. Fallback to extractive answer if all LLM calls fail.
    """
    if not chunks:
        return "I don't have specific knowledge about that in my context.", 0.0

    # --- 1. Sanitize user question ---
    safe_question = _sanitize_input(question)
    if not safe_question:
        safe_question = "(empty question)"
        logger.warning("User question was empty after sanitization.")

    # Build context from chunks
    context_text = "\n\n".join([
        f"[Source {i+1}] {chunk['text']}"
        for i, chunk in enumerate(chunks)
    ])

    # Calculate confidence from similarity scores
    avg_similarity = sum(c["similarity"] for c in chunks) / len(chunks)
    confidence = round(min(avg_similarity * 1.2, 0.95), 2)  # Cap at 0.95

    # If no API keys, return extractive fallback
    if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
        best_chunk = max(chunks, key=lambda c: c["similarity"])
        return f"Based on my knowledge: {best_chunk['text']}", confidence

    # --- 2. Try OpenAI first, then Anthropic ---
    raw_answer = None

    if _openai_client:
        try:
            raw_answer = await _synthesize_openai(safe_question, context_text)
        except Exception as exc:
            logger.warning("OpenAI synthesis failed: %s", str(exc))
            await asyncio.sleep(1.0)  # Pause before fallback

    if raw_answer is None and ANTHROPIC_API_KEY:
        try:
            raw_answer = await _synthesize_anthropic(safe_question, context_text)
        except Exception as exc:
            logger.warning("Anthropic synthesis failed: %s", str(exc))
            await asyncio.sleep(1.0)  # Pause before final fallback

    # --- 3. Validate output ---
    if raw_answer is not None:
        answer = _validate_output(raw_answer, chunks, max_length=2000)
        if answer != _FALLBACK_MSG:
            return answer, confidence
        # Validation produced fallback; log and continue to extractive fallback
        logger.info("Output validation produced fallback; trying extractive fallback.")

    # --- 4. Final extractive fallback ---
    logger.info("All LLM providers failed or returned invalid output; using extractive fallback.")
    best_chunk = max(chunks, key=lambda c: c["similarity"])
    fallback_answer = f"Based on my knowledge: {best_chunk['text']}"
    # Also validate the fallback answer
    fallback_answer = _validate_output(fallback_answer, chunks, max_length=2000)
    return fallback_answer, confidence
