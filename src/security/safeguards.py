"""Safeguards — blocklist, never-auto-reply, rate limiting, sensitive topics, master pre-send check."""

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import select

from src.config import settings
from src.db.models import Setting, Thread
from src.db.session import async_session
from src.security.audit import log_action, log_security_event
from src.security.commitment_detector import detect_commitments

logger = logging.getLogger("ghostpost.security.safeguards")

# Sensitive topic keywords
SENSITIVE_TOPICS = {
    "legal", "lawsuit", "attorney", "lawyer", "litigation", "court",
    "tax", "irs", "audit",
    "medical", "hipaa", "diagnosis", "prescription",
    "confidential", "classified", "nda",
    "termination", "fired", "layoff",
    "harassment", "discrimination", "complaint",
}


# --- Settings CRUD (blocklist, never-auto-reply stored as JSON arrays) ---

async def _get_setting(key: str) -> list[str]:
    """Get a setting value as a list."""
    async with async_session() as session:
        setting = await session.get(Setting, key)
        if not setting or not setting.value:
            return []
        try:
            return json.loads(setting.value)
        except json.JSONDecodeError:
            return []


async def _set_setting(key: str, value: list[str]) -> None:
    """Set a setting value from a list."""
    async with async_session() as session:
        setting = await session.get(Setting, key)
        if setting:
            setting.value = json.dumps(value)
        else:
            session.add(Setting(key=key, value=json.dumps(value)))
        await session.commit()


# --- Blocklist ---

async def get_blocklist() -> list[str]:
    return await _get_setting("blocklist")


async def add_to_blocklist(email: str, actor: str = "user") -> None:
    bl = await get_blocklist()
    if email.lower() not in [e.lower() for e in bl]:
        bl.append(email.lower())
        await _set_setting("blocklist", bl)
        await log_action("blocklist_add", actor=actor, details={"email": email})


async def remove_from_blocklist(email: str, actor: str = "user") -> None:
    bl = await get_blocklist()
    bl = [e for e in bl if e.lower() != email.lower()]
    await _set_setting("blocklist", bl)
    await log_action("blocklist_remove", actor=actor, details={"email": email})


async def is_blocked(email: str) -> bool:
    bl = await get_blocklist()
    return email.lower() in [e.lower() for e in bl]


# --- Never-Auto-Reply ---

async def get_never_auto_reply() -> list[str]:
    return await _get_setting("never_auto_reply")


async def add_never_auto_reply(email: str, actor: str = "user") -> None:
    nar = await get_never_auto_reply()
    if email.lower() not in [e.lower() for e in nar]:
        nar.append(email.lower())
        await _set_setting("never_auto_reply", nar)
        await log_action("never_auto_reply_add", actor=actor, details={"email": email})


async def remove_never_auto_reply(email: str, actor: str = "user") -> None:
    nar = await get_never_auto_reply()
    nar = [e for e in nar if e.lower() != email.lower()]
    await _set_setting("never_auto_reply", nar)
    await log_action("never_auto_reply_remove", actor=actor, details={"email": email})


# --- Sensitive Topics ---

def check_sensitive_topics(text: str) -> list[str]:
    """Check text for sensitive topic keywords. Returns list of matched keywords."""
    if not text:
        return []
    text_lower = text.lower()
    return [topic for topic in SENSITIVE_TOPICS if topic in text_lower]


# --- Rate Limiter ---

async def check_rate_limit(actor: str = "system", limit: int = 20) -> dict:
    """Check hourly send rate. Returns {allowed: bool, count: int, limit: int}."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        now = datetime.now(timezone.utc)
        key = f"ghostpost:rate:{actor}:{now.strftime('%Y%m%d%H')}"
        count = await r.get(key)
        count = int(count) if count else 0
        return {"allowed": count < limit, "count": count, "limit": limit}
    finally:
        await r.aclose()


async def increment_rate(actor: str = "system") -> int:
    """Increment the hourly send counter. Returns new count."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        now = datetime.now(timezone.utc)
        key = f"ghostpost:rate:{actor}:{now.strftime('%Y%m%d%H')}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, 3600)
        return count
    finally:
        await r.aclose()


# --- Master Pre-Send Check ---

async def check_send_allowed(
    to: str | list[str],
    body: str = "",
    thread_id: int | None = None,
    actor: str = "system",
    rate_limit: int = 20,
) -> dict:
    """Master pre-send check. Returns {allowed: bool, reasons: list[str], warnings: list[str]}.

    Checks:
    1. Blocklist — hard block
    2. Rate limit — hard block
    3. Commitment detection — warning
    4. Sensitive topics — warning
    5. Security score — warning if thread score < 50
    """
    reasons = []  # Hard blocks
    warnings = []  # Soft warnings (allow but flag)

    to_list = [to] if isinstance(to, str) else to

    # 1. Blocklist check
    for addr in to_list:
        if await is_blocked(addr):
            reasons.append(f"Recipient {addr} is on the blocklist")

    # 2. Rate limit
    rate = await check_rate_limit(actor, limit=rate_limit)
    if not rate["allowed"]:
        reasons.append(f"Hourly send limit exceeded ({rate['count']}/{rate['limit']})")
        await log_security_event(
            event_type="rate_limit_exceeded",
            severity="high",
            thread_id=thread_id,
            details={"actor": actor, "count": rate["count"], "limit": rate["limit"]},
        )

    # 3. Commitment detection
    commitments = detect_commitments(body)
    if commitments:
        for c in commitments:
            warnings.append(f"Commitment detected: {c['description']} ({c['matched_text']})")

    # 4. Sensitive topics
    sensitive = check_sensitive_topics(body)
    if sensitive:
        warnings.append(f"Sensitive topics detected: {', '.join(sensitive)}")

    # 5. Security score check (if thread provided)
    if thread_id:
        async with async_session() as session:
            thread = await session.get(Thread, thread_id)
            if thread and thread.security_score_avg is not None and thread.security_score_avg < 50:
                warnings.append(f"Low security score on thread: {thread.security_score_avg}/100")

    allowed = len(reasons) == 0

    if not allowed:
        logger.warning(f"Send blocked to {to_list}: {reasons}")
    elif warnings:
        logger.info(f"Send allowed with warnings to {to_list}: {warnings}")

    return {"allowed": allowed, "reasons": reasons, "warnings": warnings}
