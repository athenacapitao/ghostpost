"""Event publishing via Redis pub/sub."""

import json
import logging

import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger("ghostpost.events")

CHANNEL = "ghostpost:events"


async def publish_event(event_type: str, data: dict):
    """Publish an event to Redis pub/sub."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        message = json.dumps({"type": event_type, "data": data})
        await r.publish(CHANNEL, message)
        logger.debug(f"Published event: {event_type}")
    finally:
        await r.aclose()
