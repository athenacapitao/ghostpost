import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from src.config import settings
from src.db.session import engine

router = APIRouter()


@router.get("/api/health")
async def health_check() -> dict:
    """Return liveness status of the API, database, and Redis."""
    db_ok = False
    redis_ok = False

    # Check database connectivity
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Check Redis connectivity
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {"status": status, "db": db_ok, "redis": redis_ok}
