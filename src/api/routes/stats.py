"""Stats endpoint — storage and counts."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from src.api.dependencies import get_current_user
from src.api.schemas import StatsOut
from src.db.models import Attachment, Contact, Email, Thread
from src.db.session import async_session

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
async def get_stats(_user: str = Depends(get_current_user)):
    async with async_session() as session:
        threads = (await session.execute(select(func.count(Thread.id)))).scalar() or 0
        active_threads = (
            await session.execute(
                select(func.count(Thread.id)).where(Thread.state != "ARCHIVED")
            )
        ).scalar() or 0
        archived_threads = threads - active_threads
        emails = (await session.execute(select(func.count(Email.id)))).scalar() or 0
        contacts = (await session.execute(select(func.count(Contact.id)))).scalar() or 0
        attachments = (await session.execute(select(func.count(Attachment.id)))).scalar() or 0
        unread = (
            await session.execute(
                select(func.count(Email.id)).where(Email.is_read == False)  # noqa: E712
            )
        ).scalar() or 0

        # Database size in MB
        result = await session.execute(
            text("SELECT pg_database_size(current_database()) / 1048576.0")
        )
        db_size_mb = round(result.scalar() or 0, 2)

    return StatsOut(
        total_threads=threads,
        active_threads=active_threads,
        archived_threads=archived_threads,
        total_emails=emails,
        total_contacts=contacts,
        total_attachments=attachments,
        unread_emails=unread,
        db_size_mb=db_size_mb,
    )
