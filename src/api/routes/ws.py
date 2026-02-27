"""WebSocket endpoint for real-time updates."""

import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.api.auth import decode_token
from src.api.events import CHANNEL
from src.config import settings

logger = logging.getLogger("ghostpost.ws")

router = APIRouter()


@router.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    """WebSocket with JWT auth via query param. Subscribes to Redis pub/sub."""
    # Authenticate
    try:
        payload = decode_token(token)
        if payload.get("sub") != settings.ADMIN_USERNAME:
            await ws.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await ws.close(code=4001, reason="Invalid token")
        return

    await ws.accept()
    logger.info("WebSocket client connected")

    r = aioredis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(CHANNEL)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await ws.send_text(data)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
        await r.aclose()
