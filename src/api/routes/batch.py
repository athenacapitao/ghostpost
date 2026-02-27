"""Batch job API routes — list, detail, cancel."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from src.api.dependencies import get_current_user
from src.api.schemas import BatchJobDetailOut, BatchJobOut
from src.db.models import BatchJob
from src.db.session import async_session

router = APIRouter(prefix="/api", tags=["batch"])


@router.get("/batch", response_model=list[BatchJobOut])
async def list_batch_jobs(_user: str = Depends(get_current_user)):
    """List all batch jobs, newest first."""
    async with async_session() as session:
        result = await session.execute(
            select(BatchJob).order_by(BatchJob.created_at.desc())
        )
        jobs = result.scalars().all()
    return jobs


@router.get("/batch/{batch_id}", response_model=BatchJobDetailOut)
async def get_batch_job(batch_id: int, _user: str = Depends(get_current_user)):
    """Get batch job detail with items."""
    async with async_session() as session:
        job = await session.get(BatchJob, batch_id)
        if not job:
            raise HTTPException(status_code=404, detail="Batch job not found")
    return job


@router.post("/batch/{batch_id}/cancel", response_model=BatchJobOut)
async def cancel_batch_job(batch_id: int, _user: str = Depends(get_current_user)):
    """Cancel a pending/in_progress batch job."""
    from src.engine.batch import cancel_batch

    try:
        job = await cancel_batch(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return job
