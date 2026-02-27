"""Outcomes endpoints — knowledge extraction for completed threads."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_user
from src.api.schemas import ThreadOutcomeOut
from src.db.models import Thread
from src.db.session import async_session
from src.engine.knowledge import get_outcome, list_outcomes, on_thread_complete

router = APIRouter(prefix="/api", tags=["outcomes"])


@router.post("/threads/{thread_id}/extract", response_model=ThreadOutcomeOut)
async def extract_thread_outcome(
    thread_id: int,
    _user: str = Depends(get_current_user),
):
    """Trigger knowledge extraction for a completed thread.

    The thread must be in GOAL_MET or ARCHIVED state. Returns the outcome record,
    or 404 if the thread does not exist. Returns 409 if an outcome already exists.
    """
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        if thread.state not in ("GOAL_MET", "ARCHIVED"):
            raise HTTPException(
                status_code=400,
                detail=f"Thread must be in GOAL_MET or ARCHIVED state (current: {thread.state})",
            )

    # Check if already extracted
    existing = await get_outcome(thread_id)
    if existing:
        raise HTTPException(status_code=409, detail="Outcome already extracted for this thread")

    filename = await on_thread_complete(thread_id)
    if not filename:
        raise HTTPException(status_code=503, detail="Extraction failed — LLM unavailable or no emails")

    outcome = await get_outcome(thread_id)
    if not outcome:
        raise HTTPException(status_code=500, detail="Extraction succeeded but outcome record not found")
    return outcome


@router.get("/outcomes", response_model=list[ThreadOutcomeOut])
async def get_all_outcomes(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: str = Depends(get_current_user),
):
    """List all extracted thread outcomes, most recent first."""
    return await list_outcomes(limit=limit, offset=offset)


@router.get("/outcomes/{thread_id}", response_model=ThreadOutcomeOut)
async def get_thread_outcome(
    thread_id: int,
    _user: str = Depends(get_current_user),
):
    """Get the extracted outcome for a specific thread."""
    outcome = await get_outcome(thread_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome found for this thread")
    return outcome
