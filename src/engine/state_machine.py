"""Thread state machine — manages thread lifecycle states."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.db.models import Thread
from src.db.session import async_session
from src.security.audit import log_action
from src.api.events import publish_event

logger = logging.getLogger("ghostpost.engine.state_machine")

# Valid states
STATES = {"NEW", "ACTIVE", "WAITING_REPLY", "FOLLOW_UP", "GOAL_MET", "ARCHIVED"}


async def transition(
    thread_id: int,
    new_state: str,
    reason: str | None = None,
    actor: str = "system",
) -> str | None:
    """Transition a thread to a new state. Returns old state or None if thread not found."""
    if new_state not in STATES:
        raise ValueError(f"Invalid state: {new_state}. Must be one of {STATES}")

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return None

        old_state = thread.state
        if old_state == new_state:
            return old_state

        thread.state = new_state
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="state_changed",
        thread_id=thread_id,
        actor=actor,
        details={"old_state": old_state, "new_state": new_state, "reason": reason},
    )

    await publish_event("state_changed", {
        "thread_id": thread_id,
        "old_state": old_state,
        "new_state": new_state,
        "reason": reason,
    })

    logger.info(f"Thread {thread_id}: {old_state} -> {new_state} ({reason or 'no reason'})")

    # Trigger knowledge extraction on thread completion
    if new_state in ("GOAL_MET", "ARCHIVED"):
        try:
            from src.engine.knowledge import on_thread_complete
            asyncio.create_task(on_thread_complete(thread_id))
        except Exception as e:
            logger.error(f"Failed to trigger knowledge extraction: {e}")

    return old_state


async def auto_transition_on_send(thread_id: int) -> str | None:
    """After sending a reply, move thread to WAITING_REPLY and set follow-up date."""
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return None

        old_state = thread.state
        thread.state = "WAITING_REPLY"
        thread.next_follow_up_date = datetime.now(timezone.utc) + timedelta(days=thread.follow_up_days)
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="state_changed",
        thread_id=thread_id,
        actor="system",
        details={
            "old_state": old_state,
            "new_state": "WAITING_REPLY",
            "reason": "reply_sent",
            "follow_up_date": thread.next_follow_up_date.isoformat(),
        },
    )

    await publish_event("state_changed", {
        "thread_id": thread_id,
        "old_state": old_state,
        "new_state": "WAITING_REPLY",
    })

    logger.info(f"Thread {thread_id}: {old_state} -> WAITING_REPLY (reply sent, follow-up in {thread.follow_up_days} days)")
    return old_state


async def auto_transition_on_receive(thread_id: int) -> str | None:
    """When a new email arrives, move WAITING_REPLY/FOLLOW_UP threads to ACTIVE."""
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return None

        if thread.state not in ("WAITING_REPLY", "FOLLOW_UP"):
            return thread.state

        old_state = thread.state
        thread.state = "ACTIVE"
        thread.next_follow_up_date = None  # Clear follow-up since we got a response
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="state_changed",
        thread_id=thread_id,
        actor="system",
        details={
            "old_state": old_state,
            "new_state": "ACTIVE",
            "reason": "email_received",
        },
    )

    await publish_event("state_changed", {
        "thread_id": thread_id,
        "old_state": old_state,
        "new_state": "ACTIVE",
    })

    logger.info(f"Thread {thread_id}: {old_state} -> ACTIVE (new email received)")
    return old_state


async def get_threads_needing_follow_up() -> list[int]:
    """Get thread IDs where follow-up date has passed."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        result = await session.execute(
            select(Thread.id).where(
                Thread.state == "WAITING_REPLY",
                Thread.next_follow_up_date <= now,
                Thread.next_follow_up_date.isnot(None),
            )
        )
        return list(result.scalars().all())
