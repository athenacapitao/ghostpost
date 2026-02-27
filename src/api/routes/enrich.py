"""Enrichment trigger and status endpoints."""

import asyncio

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user
from src.engine.enrichment import is_running, run_full_enrichment
from src.engine.llm import llm_available

router = APIRouter(prefix="/api/enrich", tags=["enrich"])


@router.post("")
async def trigger_enrichment(_user: str = Depends(get_current_user)):
    """Trigger full enrichment pipeline (background)."""
    if is_running():
        return {"message": "Enrichment already in progress"}

    asyncio.create_task(run_full_enrichment())
    return {
        "message": "Enrichment started",
        "llm_available": llm_available(),
    }


@router.get("/status")
async def enrichment_status(_user: str = Depends(get_current_user)):
    return {
        "running": is_running(),
        "llm_available": llm_available(),
    }
