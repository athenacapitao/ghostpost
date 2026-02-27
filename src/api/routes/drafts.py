"""Draft management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from src.api.dependencies import get_current_user
from src.api.schemas import DraftOut
from src.db.models import Draft
from src.db.session import async_session

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("", response_model=list[DraftOut])
async def list_drafts(
    status: str = Query("pending"),
    _user: str = Depends(get_current_user),
):
    """List drafts, optionally filtered by status."""
    async with async_session() as session:
        q = select(Draft).order_by(Draft.created_at.desc())
        if status:
            q = q.where(Draft.status == status)
        result = await session.execute(q)
        return result.scalars().all()


@router.post("/{draft_id}/approve")
async def approve_draft_endpoint(
    draft_id: int,
    _user: str = Depends(get_current_user),
):
    """Approve and send a pending draft."""
    from src.gmail.send import approve_draft
    from src.engine.state_machine import auto_transition_on_send
    from src.security.safeguards import increment_rate

    try:
        result = await approve_draft(draft_id, actor="user")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Transition thread state after send
    async with async_session() as session:
        draft = await session.get(Draft, draft_id)
        if draft and draft.thread_id:
            await auto_transition_on_send(draft.thread_id)

    await increment_rate("user")
    return {"message": "Draft approved and sent", "gmail_id": result.get("id")}


@router.post("/{draft_id}/reject")
async def reject_draft_endpoint(
    draft_id: int,
    _user: str = Depends(get_current_user),
):
    """Reject a pending draft."""
    from src.gmail.send import reject_draft

    try:
        await reject_draft(draft_id, actor="user")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Draft rejected"}
