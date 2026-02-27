import asyncio
import logging
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text

from src.api.routes.batch import router as batch_router
from src.api.routes.attachments import router as attachments_router
from src.api.routes.notifications import router as notifications_router
from src.api.routes.outcomes import router as outcomes_router
from src.api.routes.audit import router as audit_router
from src.api.routes.settings import router as settings_router
from src.api.routes.auth import router as auth_router
from src.api.routes.compose import router as compose_router
from src.api.routes.contacts import router as contacts_router
from src.api.routes.drafts import router as drafts_router
from src.api.routes.emails import router as emails_router
from src.api.routes.enrich import router as enrich_router
from src.api.routes.playbooks import router as playbooks_router
from src.api.routes.health import router as health_router
from src.api.routes.security import router as security_router
from src.api.routes.stats import router as stats_router
from src.api.routes.sync import router as sync_router
from src.api.routes.threads import router as threads_router
from src.api.routes.research import router as research_router
from src.api.routes.triage import router as triage_router
from src.api.routes.ws import router as ws_router
from src.config import settings
from src.db.models import Email
from src.db.session import async_session, engine
from src.gmail.scheduler import start_scheduler, stop_scheduler
from src.gmail.sync import sync_engine

from src.logging_config import setup_logging

setup_logging(log_level=settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
logger = logging.getLogger("ghostpost")


async def _first_run_sync():
    """Check if DB is empty and kick off full sync if so."""
    try:
        async with async_session() as session:
            result = await session.execute(select(func.count(Email.id)))
            count = result.scalar()
        if count == 0:
            logger.info("Empty database — starting full sync")
            await sync_engine.full_sync()
        else:
            logger.info(f"Database has {count} emails — skipping full sync")
            # Still grab the current history ID for incremental syncs
            profile = await sync_engine.client.get_profile()
            sync_engine.status["last_history_id"] = profile.get("historyId")
    except Exception as e:
        logger.error(f"First-run sync failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("GhostPost starting up...")

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connected")

    r = aioredis.from_url(settings.REDIS_URL)
    await r.ping()
    await r.aclose()
    logger.info("Redis connected")

    # Start sync scheduler
    start_scheduler()

    # Resume any in-progress batch jobs (email batches)
    from src.engine.batch import resume_pending_batches
    asyncio.create_task(resume_pending_batches())

    # Resume any in-progress research batches
    from src.research.queue import resume_research_batches
    asyncio.create_task(resume_research_batches())

    # First-run full sync as background task
    asyncio.create_task(_first_run_sync())

    logger.info("GhostPost ready")
    yield

    stop_scheduler()
    await engine.dispose()
    logger.info("GhostPost shut down")


app = FastAPI(title="GhostPost", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ghostpost.work"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(threads_router)
app.include_router(emails_router)
app.include_router(contacts_router)
app.include_router(sync_router)
app.include_router(stats_router)
app.include_router(attachments_router)
app.include_router(enrich_router)
app.include_router(playbooks_router)
app.include_router(drafts_router)
app.include_router(compose_router)
app.include_router(security_router)
app.include_router(audit_router)
app.include_router(settings_router)
app.include_router(notifications_router)
app.include_router(outcomes_router)
app.include_router(batch_router)
app.include_router(research_router)
app.include_router(triage_router)
app.include_router(ws_router)

# Serve frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="static")

    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        """Serve the React SPA for all non-API routes."""
        file_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
