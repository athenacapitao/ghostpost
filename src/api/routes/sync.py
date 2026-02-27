"""Sync trigger and status endpoints."""

import asyncio

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user
from src.api.schemas import SyncStatusOut, SyncTriggerResponse
from src.gmail.sync import sync_engine

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("", response_model=SyncTriggerResponse)
async def trigger_sync(_user: str = Depends(get_current_user)):
    if sync_engine.status["running"]:
        return SyncTriggerResponse(message="Sync already in progress")

    asyncio.create_task(sync_engine.incremental_sync())
    return SyncTriggerResponse(message="Sync started")


@router.get("/status", response_model=SyncStatusOut)
async def sync_status(_user: str = Depends(get_current_user)):
    return SyncStatusOut(**sync_engine.status)
