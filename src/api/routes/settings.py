"""Settings CRUD API — key-value configuration management."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from src.api.dependencies import get_current_user
from src.db.models import Setting
from src.db.session import async_session

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "reply_style": "professional",
    "reply_style_custom": "",
    "default_follow_up_days": "3",
    "commitment_threshold": "500",
    "notification_new_email": "true",
    "notification_goal_met": "true",
    "notification_security_alert": "true",
    "notification_draft_ready": "true",
    "notification_stale_thread": "true",
}


class SettingValue(BaseModel):
    value: str


class BulkSettings(BaseModel):
    settings: dict[str, str]


@router.get("")
async def list_settings(_user: str = Depends(get_current_user)) -> dict[str, str]:
    """Get all settings as a key-value dict."""
    async with async_session() as session:
        result = await session.execute(select(Setting))
        rows = result.scalars().all()
    stored = {r.key: r.value for r in rows}
    return {**DEFAULTS, **stored}


@router.put("/bulk")
async def bulk_update(body: BulkSettings, _user: str = Depends(get_current_user)) -> dict:
    """Update multiple settings at once."""
    invalid = set(body.settings.keys()) - set(DEFAULTS.keys())
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown settings: {', '.join(invalid)}")
    async with async_session() as session:
        for key, value in body.settings.items():
            setting = await session.get(Setting, key)
            if setting:
                setting.value = value
            else:
                session.add(Setting(key=key, value=value))
        await session.commit()
    return {"updated": list(body.settings.keys())}


@router.get("/{key}")
async def get_setting(key: str, _user: str = Depends(get_current_user)) -> dict:
    """Get a single setting by key."""
    async with async_session() as session:
        setting = await session.get(Setting, key)
    if setting:
        return {"key": key, "value": setting.value}
    if key in DEFAULTS:
        return {"key": key, "value": DEFAULTS[key]}
    raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")


@router.put("/{key}")
async def update_setting(key: str, body: SettingValue, _user: str = Depends(get_current_user)) -> dict:
    """Create or update a setting."""
    async with async_session() as session:
        setting = await session.get(Setting, key)
        if setting:
            setting.value = body.value
        else:
            session.add(Setting(key=key, value=body.value))
        await session.commit()
    return {"key": key, "value": body.value}


@router.delete("/{key}")
async def delete_setting(key: str, _user: str = Depends(get_current_user)) -> dict:
    """Delete a setting (resets to default if one exists)."""
    async with async_session() as session:
        setting = await session.get(Setting, key)
        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
        await session.delete(setting)
        await session.commit()
    return {"message": f"Setting '{key}' deleted"}
