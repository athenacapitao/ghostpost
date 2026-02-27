"""Thread endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from src.api.dependencies import get_current_user
from src.api.schemas import (
    ThreadDetailOut,
    ThreadListResponse,
    ThreadSummaryOut,
    ReplyRequest,
    DraftRequest,
    StateRequest,
    AutoReplyRequest,
    FollowUpRequest,
    NotesRequest,
    GoalRequest,
    GoalStatusRequest,
)
from src.db.models import Email, Thread
from src.db.session import async_session
from src.engine.brief import generate_brief

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: str | None = None,
    q: str | None = None,
    _user: str = Depends(get_current_user),
):
    async with async_session() as session:
        # Base query
        base = select(Thread)
        count_q = select(func.count(Thread.id))

        if state:
            base = base.where(Thread.state == state)
            count_q = count_q.where(Thread.state == state)
        if q:
            base = base.where(Thread.subject.ilike(f"%{q}%"))
            count_q = count_q.where(Thread.subject.ilike(f"%{q}%"))

        # Get total count
        total = (await session.execute(count_q)).scalar() or 0

        # Get page
        threads = (
            await session.execute(
                base.order_by(Thread.last_activity_at.desc().nullslast())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        # Get email counts per thread
        items = []
        for t in threads:
            email_count = (
                await session.execute(
                    select(func.count(Email.id)).where(Email.thread_id == t.id)
                )
            ).scalar() or 0
            item = ThreadSummaryOut.model_validate(t)
            item.email_count = email_count
            items.append(item)

        return ThreadListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total > 0 else 0,
        )


@router.get("/{thread_id}", response_model=ThreadDetailOut)
async def get_thread(thread_id: int, _user: str = Depends(get_current_user)):
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Emails loaded via selectin relationship
        return ThreadDetailOut.model_validate(thread)


@router.get("/{thread_id}/brief", response_class=PlainTextResponse)
async def get_thread_brief(thread_id: int, _user: str = Depends(get_current_user)):
    """Get a structured markdown brief for a thread (agent consumption)."""
    brief = await generate_brief(thread_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Thread not found")
    return brief


@router.post("/{thread_id}/reply")
async def reply_to_thread(
    thread_id: int,
    req: ReplyRequest,
    draft: bool = Query(False, description="Save as draft instead of sending"),
    _user: str = Depends(get_current_user),
):
    """Send a reply to the latest email in a thread.

    When draft=True, the reply body is saved as a Gmail draft and no email is
    sent.  Safeguard checks and state transitions are skipped because the draft
    must be explicitly approved before it leaves the system.
    """
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

    # Get the last email — needed both for the safeguard recipient check and
    # for resolving the To/Subject when creating a draft.
    async with async_session() as session:
        last_email = (await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.desc())
            .limit(1)
        )).scalar_one_or_none()

    if draft:
        # Draft path — no safeguards, no state transition.  Safeguards run at
        # approve time instead so the agent can review first.
        from src.gmail.send import create_draft

        to = last_email.from_address if last_email else ""
        raw_subject = (last_email.subject or "") if last_email else ""
        subject = raw_subject if raw_subject.lower().startswith("re:") else f"Re: {raw_subject}"

        saved_draft = await create_draft(
            thread_id,
            to=[to],
            subject=subject,
            body=req.body,
            cc=req.cc,
            bcc=req.bcc,
            actor="user",
        )
        return {
            "message": "Draft created",
            "draft_id": saved_draft.id,
        }

    # Send path — existing behaviour unchanged.
    from src.security.safeguards import check_send_allowed, increment_rate
    from src.gmail.send import send_reply
    from src.engine.state_machine import auto_transition_on_send

    check = {"allowed": True, "reasons": [], "warnings": []}
    if last_email:
        check = await check_send_allowed(
            to=last_email.from_address or "",
            body=req.body,
            thread_id=thread_id,
        )
        if not check["allowed"]:
            raise HTTPException(
                status_code=403,
                detail={"blocked": True, "reasons": check["reasons"]},
            )

    result = await send_reply(thread_id, req.body, cc=req.cc, bcc=req.bcc, actor="user")
    await auto_transition_on_send(thread_id)
    await increment_rate("user")

    return {
        "message": "Reply sent",
        "gmail_id": result.get("id"),
        "warnings": check.get("warnings", []),
    }


@router.post("/{thread_id}/draft")
async def create_thread_draft(
    thread_id: int,
    req: DraftRequest,
    _user: str = Depends(get_current_user),
):
    """Create a draft reply for a thread."""
    from src.gmail.send import create_draft

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

    to = req.to if isinstance(req.to, list) else [req.to]
    draft = await create_draft(
        thread_id, to, req.subject, req.body, cc=req.cc, bcc=req.bcc, actor="user"
    )
    return {"message": "Draft created", "draft_id": draft.id}


@router.put("/{thread_id}/state")
async def update_thread_state(
    thread_id: int,
    req: StateRequest,
    _user: str = Depends(get_current_user),
):
    """Update thread state."""
    from src.engine.state_machine import transition, STATES

    if req.state not in STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state. Must be one of: {sorted(STATES)}",
        )
    old = await transition(thread_id, req.state, reason=req.reason, actor="user")
    if old is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"old_state": old, "new_state": req.state}


@router.put("/{thread_id}/auto-reply")
async def update_auto_reply(
    thread_id: int,
    req: AutoReplyRequest,
    _user: str = Depends(get_current_user),
):
    """Set auto-reply mode for a thread."""
    if req.mode not in ("off", "draft", "auto"):
        raise HTTPException(status_code=400, detail="Mode must be: off, draft, auto")
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread.auto_reply_mode = req.mode
        await session.commit()
    from src.security.audit import log_action
    await log_action(
        "auto_reply_changed",
        thread_id=thread_id,
        actor="user",
        details={"mode": req.mode},
    )
    return {"thread_id": thread_id, "auto_reply_mode": req.mode}


@router.put("/{thread_id}/follow-up")
async def update_follow_up(
    thread_id: int,
    req: FollowUpRequest,
    _user: str = Depends(get_current_user),
):
    """Set follow-up days for a thread."""
    from src.engine.followup import set_follow_up

    ok = await set_follow_up(thread_id, req.days, actor="user")
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread_id": thread_id, "follow_up_days": req.days}


@router.put("/{thread_id}/notes")
async def update_notes(
    thread_id: int,
    req: NotesRequest,
    _user: str = Depends(get_current_user),
):
    """Update thread notes."""
    from datetime import datetime, timezone

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread.notes = req.notes
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()
    return {"thread_id": thread_id, "notes": req.notes}


@router.put("/{thread_id}/goal")
async def set_thread_goal(
    thread_id: int,
    req: GoalRequest,
    _user: str = Depends(get_current_user),
):
    """Set a goal for a thread."""
    from src.engine.goals import set_goal

    ok = await set_goal(
        thread_id, req.goal, req.acceptance_criteria, actor="user"
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"thread_id": thread_id, "goal": req.goal}


@router.delete("/{thread_id}/goal")
async def delete_thread_goal(
    thread_id: int,
    _user: str = Depends(get_current_user),
):
    """Remove goal from a thread."""
    from src.engine.goals import clear_goal

    ok = await clear_goal(thread_id, actor="user")
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"message": "Goal cleared"}


@router.put("/{thread_id}/goal/status")
async def update_goal_status_endpoint(
    thread_id: int,
    req: GoalStatusRequest,
    _user: str = Depends(get_current_user),
):
    """Update goal status."""
    from src.engine.goals import update_goal_status

    try:
        ok = await update_goal_status(thread_id, req.status, actor="user")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found or no goal set")
    return {"thread_id": thread_id, "goal_status": req.status}


@router.post("/{thread_id}/generate-reply")
async def generate_thread_reply(
    thread_id: int,
    instructions: str | None = None,
    style: str | None = None,
    create_draft: bool = Query(False, description="Save the generated reply as a Gmail draft"),
    _user: str = Depends(get_current_user),
):
    """Generate a reply using LLM with the configured reply style.

    When create_draft=True, the generated body is also saved as a Gmail draft
    and the response includes the draft_id alongside the generated content.
    """
    from src.engine.composer import generate_reply

    result = await generate_reply(thread_id, instructions=instructions, style_override=style)
    if "error" in result:
        status_code = 404 if result["error"] == "Thread not found" else 503
        raise HTTPException(status_code=status_code, detail=result["error"])

    if create_draft:
        from src.gmail.send import create_draft as _create_draft

        subject = result.get("subject", "")
        to = result.get("to", "")
        body = result.get("body", "")

        saved_draft = await _create_draft(
            thread_id,
            to=[to],
            subject=subject,
            body=body,
            actor="user",
        )
        result["draft_id"] = saved_draft.id

    return result


@router.post("/{thread_id}/goal/check")
async def check_goal_met_endpoint(
    thread_id: int,
    _user: str = Depends(get_current_user),
):
    """Use LLM to check if thread goal has been met."""
    from src.engine.goals import check_goal_met

    result = await check_goal_met(thread_id)
    return result
