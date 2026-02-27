"""Notification endpoints — view alerts written for OpenClaw consumption."""

import os

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user
from src.engine.notifications import ALERTS_FILE

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/alerts")
async def get_alerts(_user: str = Depends(get_current_user)) -> dict:
    """Return the parsed list of active alerts from ALERTS.md.

    Each alert is a raw markdown string entry. The count reflects how many
    alerts are currently recorded in the file.
    """
    if not os.path.isfile(ALERTS_FILE):
        return {"alerts": [], "count": 0}

    with open(ALERTS_FILE) as f:
        content = f.read()

    alerts: list[str] = []
    for part in content.split("\n- "):
        stripped = part.strip()
        # Skip the header block and metadata lines before the first entry
        if stripped and not stripped.startswith("#") and not stripped.startswith("_"):
            alerts.append(stripped)

    return {"alerts": alerts, "count": len(alerts)}
