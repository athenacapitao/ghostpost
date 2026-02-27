"""Compose new email endpoint."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.api.dependencies import get_current_user
from src.api.schemas import ComposeRequest
from src.engine.batch import create_batch_job
from src.engine.brief import generate_brief
from src.engine.notifications import notify_thread_composed
from src.gmail.send import create_thread_from_compose, send_new
from src.security.audit import update_audit_thread_id
from src.security.safeguards import check_send_allowed, increment_rate, is_blocked

router = APIRouter(prefix="/api", tags=["compose"])


async def _regenerate_context() -> None:
    """Regenerate context files after a new email is composed.

    Runs in the background — failures are swallowed because context files
    will be refreshed automatically on the next scheduled sync.
    """
    try:
        from src.engine.context_writer import write_all
        await write_all()
    except Exception:
        pass


@router.post("/compose")
async def compose_email(
    req: ComposeRequest,
    background_tasks: BackgroundTasks,
    _user: str = Depends(get_current_user),
):
    """Send a new email (compose). Auto-batches when >20 recipients."""
    to_list = [req.to] if isinstance(req.to, str) else req.to

    if len(to_list) > 20:
        # Batch mode — pre-validate blocklist only (rate limiting handled by batch scheduler)
        blocked = [addr for addr in to_list if await is_blocked(addr)]
        if blocked:
            raise HTTPException(
                status_code=403,
                detail={"blocked": True, "reasons": [f"Recipient {a} is on the blocklist" for a in blocked]},
            )

        try:
            job = await create_batch_job(
                to_list=to_list,
                subject=req.subject,
                body=req.body,
                cc=req.cc,
                bcc=req.bcc,
                actor="user",
            )
        except ValueError as e:
            raise HTTPException(status_code=403, detail={"blocked": True, "reasons": [str(e)]})

        return {
            "message": "Batch queued",
            "batch_id": job.id,
            "total_recipients": job.total_recipients,
            "total_clusters": job.total_clusters,
        }

    # Standard flow for <=20 recipients
    check = await check_send_allowed(to=to_list, body=req.body)
    if not check["allowed"]:
        raise HTTPException(
            status_code=403,
            detail={"blocked": True, "reasons": check["reasons"]},
        )

    result = await send_new(
        to_list, req.subject, req.body, cc=req.cc, bcc=req.bcc, actor="user"
    )
    await increment_rate("user")

    # Create Thread + Email records immediately with agent context metadata.
    thread_id = await create_thread_from_compose(
        gmail_result=result,
        to=req.to,
        subject=req.subject,
        body=req.body,
        cc=req.cc,
        goal=req.goal,
        acceptance_criteria=req.acceptance_criteria,
        playbook=req.playbook,
        auto_reply_mode=req.auto_reply_mode,
        follow_up_days=req.follow_up_days,
        priority=req.priority,
        category=req.category,
        notes=req.notes,
    )

    # Backfill thread_id on the audit entry so activity links work.
    if audit_id := result.get("_audit_id"):
        await update_audit_thread_id(audit_id, thread_id)

    # Generate markdown brief for agent consumption — best-effort, never blocks send.
    brief: str | None = None
    try:
        brief = await generate_brief(thread_id)
    except Exception:
        pass

    # Notify OpenClaw about the new thread via ALERTS.md and WebSocket.
    to_display = to_list[0] if len(to_list) == 1 else f"{to_list[0]} +{len(to_list) - 1}"
    try:
        await notify_thread_composed(thread_id, req.subject, to_display, goal=req.goal)
    except Exception:
        pass

    # Regenerate context files so agent sees the new thread immediately.
    background_tasks.add_task(_regenerate_context)

    return {
        "message": "Email sent",
        "gmail_id": result.get("id"),
        "thread_id": thread_id,
        "brief": brief,
        "warnings": check.get("warnings", []),
    }
