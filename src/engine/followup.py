"""Follow-up management — checks for overdue threads and triggers follow-ups."""

import logging
from datetime import datetime, timezone

from src.db.models import Thread
from src.db.session import async_session
from src.engine.state_machine import get_threads_needing_follow_up, transition
from src.security.audit import log_action
from src.api.events import publish_event

logger = logging.getLogger("ghostpost.engine.followup")


async def set_follow_up(thread_id: int, days: int, actor: str = "user") -> bool:
    """Set follow-up days for a thread."""
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return False
        thread.follow_up_days = days
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="follow_up_set",
        thread_id=thread_id,
        actor=actor,
        details={"days": days},
    )
    return True


async def check_follow_ups() -> list[int]:
    """Check for threads needing follow-up and transition them. Returns list of thread IDs triggered."""
    thread_ids = await get_threads_needing_follow_up()
    triggered = []

    for tid in thread_ids:
        await trigger_follow_up(tid)
        triggered.append(tid)

    if triggered:
        logger.info(f"Triggered follow-ups for {len(triggered)} threads: {triggered}")

    return triggered


async def trigger_follow_up(thread_id: int) -> None:
    """Trigger a follow-up for a specific thread."""
    await transition(thread_id, "FOLLOW_UP", reason="follow_up_overdue", actor="system")

    await publish_event("follow_up_triggered", {
        "thread_id": thread_id,
    })

    await log_action(
        action_type="follow_up_triggered",
        thread_id=thread_id,
        actor="system",
    )

    # Notify OpenClaw that this thread is stale
    try:
        from src.engine.notifications import notify_stale_thread
        async with async_session() as notify_session:
            notify_thread = await notify_session.get(Thread, thread_id)
        if notify_thread:
            await notify_stale_thread(
                thread_id,
                notify_thread.subject or "",
                notify_thread.follow_up_days,
            )
    except Exception as exc:
        logger.warning(f"Failed to dispatch stale_thread notification for thread {thread_id}: {exc}")
