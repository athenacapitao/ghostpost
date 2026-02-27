"""Contact endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from src.api.dependencies import get_current_user
from src.api.schemas import ContactListResponse, ContactOut
from src.db.models import Contact
from src.db.session import async_session

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("", response_model=ContactListResponse)
async def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    _user: str = Depends(get_current_user),
):
    async with async_session() as session:
        base = select(Contact)
        count_q = select(func.count(Contact.id))

        if q:
            pattern = f"%{q}%"
            where = Contact.email.ilike(pattern) | Contact.name.ilike(pattern)
            base = base.where(where)
            count_q = count_q.where(where)

        total = (await session.execute(count_q)).scalar() or 0

        contacts = (
            await session.execute(
                base.order_by(Contact.last_interaction.desc().nullslast())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return ContactListResponse(
            items=[ContactOut.model_validate(c) for c in contacts],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total > 0 else 0,
        )


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(contact_id: int, _user: str = Depends(get_current_user)):
    async with async_session() as session:
        contact = await session.get(Contact, contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        return ContactOut.model_validate(contact)


@router.post("/{contact_id}/enrich-web")
async def enrich_contact_web_endpoint(
    contact_id: int,
    _user: str = Depends(get_current_user),
):
    """Enrich a contact using web/domain knowledge."""
    from src.engine.contacts import enrich_contact_web
    result = await enrich_contact_web(contact_id)
    if result is None:
        raise HTTPException(status_code=503, detail="Enrichment failed or LLM unavailable")
    return result
