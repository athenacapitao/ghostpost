"""Audit log endpoints."""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_current_user
from src.api.schemas import AuditLogOut
from src.security.audit import get_recent_actions

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, le=500),
    _user: str = Depends(get_current_user),
):
    """Get recent audit log entries (up to 7 days back)."""
    return await get_recent_actions(hours=hours, limit=limit)
