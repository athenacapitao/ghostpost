"""Layer 5: Anomaly detection — rate checking and new recipient flagging."""

import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import select, func

from src.config import settings
from src.db.models import Contact
from src.db.session import async_session
from src.security.audit import log_security_event

logger = logging.getLogger("ghostpost.security.anomaly_detector")


async def check_send_rate(actor: str, limit: int = 20) -> dict:
    """Check hourly send rate for an actor. Returns {allowed: bool, count: int, limit: int}."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        now = datetime.now(timezone.utc)
        key = f"ghostpost:rate:{actor}:{now.strftime('%Y%m%d%H')}"
        count = await r.get(key)
        count = int(count) if count else 0
        return {"allowed": count < limit, "count": count, "limit": limit}
    finally:
        await r.aclose()


async def increment_send_rate(actor: str) -> int:
    """Increment send counter for the current hour. Returns new count."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        now = datetime.now(timezone.utc)
        key = f"ghostpost:rate:{actor}:{now.strftime('%Y%m%d%H')}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, 3600)  # TTL: 1 hour
        return count
    finally:
        await r.aclose()


async def check_new_recipient(to_address: str) -> bool:
    """Check if this is a never-before-seen recipient. Returns True if new."""
    async with async_session() as session:
        result = await session.execute(
            select(func.count(Contact.id)).where(Contact.email == to_address)
        )
        count = result.scalar() or 0
    return count == 0


async def check_anomalies(
    to_address: str,
    actor: str = "system",
    rate_limit: int = 20,
) -> list[dict]:
    """Run all anomaly checks. Returns list of anomaly dicts."""
    anomalies = []

    # Rate check
    rate = await check_send_rate(actor, limit=rate_limit)
    if not rate["allowed"]:
        anomalies.append({
            "type": "rate_limit_exceeded",
            "severity": "high",
            "details": f"Send rate {rate['count']}/{rate['limit']} per hour exceeded",
        })
        await log_security_event(
            event_type="rate_limit_exceeded",
            severity="high",
            details={"actor": actor, "count": rate["count"], "limit": rate["limit"]},
        )

    # New recipient check
    is_new = await check_new_recipient(to_address)
    if is_new:
        anomalies.append({
            "type": "new_recipient",
            "severity": "medium",
            "details": f"Never-before-seen recipient: {to_address}",
        })

    return anomalies
