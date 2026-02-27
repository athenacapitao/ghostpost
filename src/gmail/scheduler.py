"""APScheduler jobs for periodic Gmail sync + enrichment."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.gmail.sync import sync_engine

logger = logging.getLogger("ghostpost.gmail.scheduler")

scheduler = AsyncIOScheduler()


async def sync_job():
    """Run incremental sync + post-sync enrichment. Called by APScheduler."""
    try:
        stats = await sync_engine.incremental_sync()
        logger.info(f"Scheduled sync complete: {stats}")

        # Run post-sync enrichment (security scoring + context files always;
        # LLM tasks only if API key is configured)
        from src.engine.enrichment import run_full_enrichment
        enrichment_stats = await run_full_enrichment()
        logger.info(f"Post-sync enrichment: {enrichment_stats}")

        # Check for overdue follow-ups
        from src.engine.followup import check_follow_ups
        triggered = await check_follow_ups()
        if triggered:
            logger.info(f"Follow-ups triggered: {triggered}")
    except Exception as e:
        logger.error(f"Scheduled sync/enrichment failed: {e}")


def start_scheduler():
    """Start the 10-minute sync scheduler."""
    scheduler.add_job(sync_job, "interval", minutes=10, id="gmail_sync", replace_existing=True)
    scheduler.start()
    logger.info("Sync scheduler started (10-min interval)")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Sync scheduler stopped")
