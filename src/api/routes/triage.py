"""Triage API endpoint — single entry point for agent decision-making."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_current_user
from src.engine.triage import get_triage_data

router = APIRouter(prefix="/api/triage", tags=["triage"])


@router.get("/")
async def triage(
    limit: int = Query(10, ge=1, le=50),
    _user: str = Depends(get_current_user),
) -> dict:
    """Get a prioritized triage snapshot for agent decision-making.

    Returns a summary of inbox state plus a ranked list of actions
    the agent should take next, ordered by urgency score.
    """
    snapshot = await get_triage_data(limit=limit)
    return snapshot.to_dict()
