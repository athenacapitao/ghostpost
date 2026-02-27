"""Enrichment orchestrator — runs all AI analysis jobs."""

import logging

from src.engine.analyzer import analyze_all_unanalyzed
from src.engine.categorizer import categorize_all_uncategorized
from src.engine.contacts import enrich_all_unenriched
from src.engine.context_writer import write_all_context_files
from src.engine.llm import llm_available
from src.engine.security import score_all_unscored
from src.engine.summarizer import summarize_all_unsummarized

logger = logging.getLogger("ghostpost.engine.enrichment")

_running = False


async def run_full_enrichment() -> dict:
    """Run all enrichment jobs in sequence. Returns combined stats."""
    global _running
    if _running:
        return {"status": "already_running"}

    _running = True
    stats = {
        "security": {},
        "categories": 0,
        "summaries": 0,
        "analysis": {},
        "contacts": 0,
        "context_files": 0,
        "llm_available": llm_available(),
    }

    try:
        # 1. Security scoring (rule-based, no LLM needed)
        logger.info("Running security scoring...")
        stats["security"] = await score_all_unscored()

        # 2. Context files (always update even without LLM)
        logger.info("Writing context files...")
        paths = await write_all_context_files()
        stats["context_files"] = len(paths)

        # LLM-dependent tasks
        if llm_available():
            # 3. Categorization
            logger.info("Running categorization...")
            stats["categories"] = await categorize_all_uncategorized()

            # 4. Summarization
            logger.info("Running summarization...")
            stats["summaries"] = await summarize_all_unsummarized()

            # 5. Email analysis (sentiment, urgency, action)
            logger.info("Running email analysis...")
            stats["analysis"] = await analyze_all_unanalyzed()

            # 6. Contact enrichment
            logger.info("Running contact enrichment...")
            stats["contacts"] = await enrich_all_unenriched()

            # 7. Re-write context files with enriched data
            logger.info("Re-writing context files with enriched data...")
            await write_all_context_files()
        else:
            logger.warning("LLM not available — skipping AI enrichment tasks")

        logger.info(f"Full enrichment complete: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        stats["error"] = str(e)
        return stats
    finally:
        _running = False


def is_running() -> bool:
    return _running
