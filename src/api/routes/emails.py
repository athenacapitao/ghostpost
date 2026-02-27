"""Email endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from src.api.dependencies import get_current_user
from src.api.schemas import EmailListResponse, EmailOut
from src.db.models import Email
from src.db.session import async_session

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("/search", response_model=EmailListResponse)
async def search_emails(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: str = Depends(get_current_user),
):
    async with async_session() as session:
        pattern = f"%{q}%"
        where = or_(
            Email.subject.ilike(pattern),
            Email.body_plain.ilike(pattern),
            Email.from_address.ilike(pattern),
        )

        total = (await session.execute(select(func.count(Email.id)).where(where))).scalar() or 0

        emails = (
            await session.execute(
                select(Email)
                .where(where)
                .order_by(Email.date.desc().nullslast())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return EmailListResponse(
            items=[EmailOut.model_validate(e) for e in emails],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total > 0 else 0,
        )


@router.get("/{email_id}", response_model=EmailOut)
async def get_email(email_id: int, _user: str = Depends(get_current_user)):
    async with async_session() as session:
        email = await session.get(Email, email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        return EmailOut.model_validate(email)
