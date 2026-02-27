"""Security endpoints — events, quarantine, blocklist."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_current_user
from src.api.schemas import BlocklistRequest, SecurityEventOut
from src.db.models import SecurityEvent
from src.db.session import async_session
from src.security.audit import get_security_events, log_action
from src.security.safeguards import add_to_blocklist, get_blocklist, remove_from_blocklist

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/events", response_model=list[SecurityEventOut])
async def list_security_events(
    pending_only: bool = Query(False),
    limit: int = Query(50, le=200),
    _user: str = Depends(get_current_user),
):
    """List security events, optionally filtered to pending resolution only."""
    return await get_security_events(pending_only=pending_only, limit=limit)


@router.get("/quarantine", response_model=list[SecurityEventOut])
async def list_quarantined(
    _user: str = Depends(get_current_user),
):
    """List quarantined security events (pending resolution)."""
    return await get_security_events(pending_only=True)


@router.post("/quarantine/{event_id}/approve")
async def approve_quarantine(
    event_id: int,
    _user: str = Depends(get_current_user),
):
    """Approve a quarantined email (mark as safe)."""
    async with async_session() as session:
        event = await session.get(SecurityEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Security event not found")
        event.resolution = "approved"
        await session.commit()
        email_id = event.email_id
        thread_id = event.thread_id

    await log_action(
        "quarantine_approved",
        email_id=email_id,
        thread_id=thread_id,
        actor="user",
    )
    return {"message": "Quarantine approved"}


@router.post("/quarantine/{event_id}/dismiss")
async def dismiss_quarantine(
    event_id: int,
    _user: str = Depends(get_current_user),
):
    """Dismiss a security event."""
    async with async_session() as session:
        event = await session.get(SecurityEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Security event not found")
        event.resolution = "dismissed"
        await session.commit()
        email_id = event.email_id
        thread_id = event.thread_id

    await log_action(
        "quarantine_dismissed",
        email_id=email_id,
        thread_id=thread_id,
        actor="user",
    )
    return {"message": "Security event dismissed"}


@router.get("/blocklist")
async def list_blocklist(_user: str = Depends(get_current_user)):
    """Get the current blocklist."""
    return {"blocklist": await get_blocklist()}


@router.post("/blocklist")
async def add_blocklist(
    req: BlocklistRequest,
    _user: str = Depends(get_current_user),
):
    """Add an email address to the blocklist."""
    await add_to_blocklist(req.email, actor="user")
    return {"message": f"Added {req.email} to blocklist"}


@router.delete("/blocklist")
async def remove_blocklist(
    req: BlocklistRequest,
    _user: str = Depends(get_current_user),
):
    """Remove an email address from the blocklist."""
    await remove_from_blocklist(req.email, actor="user")
    return {"message": f"Removed {req.email} from blocklist"}
