"""LLM client via OpenClaw gateway — all requests route to agent ghostpost."""

import asyncio
import json
import logging
import time
import uuid

import httpx

from src.config import settings

logger = logging.getLogger("ghostpost.engine.llm")

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get or create the async HTTP client for the OpenClaw gateway."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.LLM_GATEWAY_URL.rsplit("/v1/chat/completions", 1)[0],
            headers={
                "Authorization": f"Bearer {settings.LLM_GATEWAY_TOKEN}",
                "Content-Type": "application/json",
                "x-openclaw-agent-id": "ghostpost",
            },
            timeout=120.0,
        )
    return _client


def llm_available() -> bool:
    """Check if the LLM gateway is configured."""
    return bool(settings.LLM_GATEWAY_TOKEN)


async def complete(
    system: str,
    user_message: str,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    timeout: float | None = None,
    retries: int = 2,
) -> str:
    """Send a chat completion request via OpenClaw gateway → ghostpost agent.

    Args:
        timeout: Per-request timeout in seconds. Defaults to client's 120s.
                 Use higher values for large prompts (e.g. research phases).
        retries: Number of retries on transient errors (timeout, 502/503/529).
    """
    client = _get_client()
    request_id = uuid.uuid4().hex[:12]
    payload = {
        "model": settings.LLM_MODEL,
        "user": settings.LLM_USER_ID,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    }

    last_exc: Exception | None = None
    for attempt in range(1 + retries):
        t0 = time.monotonic()
        try:
            response = await client.post(
                "/v1/chat/completions",
                json=payload,
                timeout=timeout,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            response.raise_for_status()
            data = response.json()
            logger.debug(
                "llm ok  req=%s model=%s status=%d latency=%dms",
                request_id, settings.LLM_MODEL, response.status_code, latency_ms,
            )
            return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            last_exc = e
            logger.warning(
                "llm timeout  req=%s attempt=%d/%d latency=%dms",
                request_id, attempt + 1, 1 + retries, latency_ms,
            )
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)
        except httpx.HTTPStatusError as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            if e.response.status_code in (502, 503, 529):
                last_exc = e
                logger.warning(
                    "llm %d  req=%s attempt=%d/%d latency=%dms",
                    e.response.status_code, request_id, attempt + 1, 1 + retries, latency_ms,
                )
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
            else:
                logger.error(
                    "llm error  req=%s status=%d latency=%dms",
                    request_id, e.response.status_code, latency_ms,
                )
                raise

    raise last_exc  # type: ignore[misc]


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from LLM response text."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the response
    import re
    match = re.search(r'\{[^{}]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try nested JSON (for action_required objects)
    match = re.search(r'\{[^}]*\{[^}]*\}[^}]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {}


async def complete_json(
    system: str,
    user_message: str,
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> dict:
    """Send a message and parse the response as JSON."""
    raw = await complete(system, user_message, max_tokens, temperature)
    result = _extract_json(raw)
    if not result:
        logger.warning(f"Failed to parse LLM JSON response: {raw[:200]}")
    return result
