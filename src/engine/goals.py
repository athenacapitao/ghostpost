"""Goal management for threads."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from src.db.models import Email, Thread
from src.db.session import async_session
from src.engine.llm import complete_json, llm_available
from src.security.audit import log_action
from src.api.events import publish_event

logger = logging.getLogger("ghostpost.engine.goals")


async def set_goal(
    thread_id: int,
    goal: str,
    acceptance_criteria: str | None = None,
    actor: str = "user",
) -> bool:
    """Set a goal for a thread."""
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return False
        thread.goal = goal
        thread.acceptance_criteria = acceptance_criteria
        thread.goal_status = "in_progress"
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="goal_set",
        thread_id=thread_id,
        actor=actor,
        details={"goal": goal, "criteria": acceptance_criteria},
    )

    await publish_event("goal_updated", {
        "thread_id": thread_id,
        "goal": goal,
        "status": "in_progress",
    })

    logger.info(f"Goal set for thread {thread_id}: {goal}")
    return True


async def update_goal_status(
    thread_id: int,
    status: str,
    actor: str = "system",
) -> bool:
    """Update goal status: in_progress, met, abandoned."""
    if status not in ("in_progress", "met", "abandoned"):
        raise ValueError(f"Invalid goal status: {status}")

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread or not thread.goal:
            return False
        old_status = thread.goal_status
        thread.goal_status = status
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="goal_status_changed",
        thread_id=thread_id,
        actor=actor,
        details={"old_status": old_status, "new_status": status},
    )

    await publish_event("goal_updated", {
        "thread_id": thread_id,
        "status": status,
    })

    # Auto-transition thread state if goal is met
    if status == "met":
        from src.engine.state_machine import transition
        await transition(thread_id, "GOAL_MET", reason="goal_met", actor="system")

        # Notify OpenClaw — load subject/goal from a fresh session to avoid stale state
        try:
            from src.engine.notifications import notify_goal_met
            async with async_session() as notify_session:
                notify_thread = await notify_session.get(Thread, thread_id)
            if notify_thread:
                await notify_goal_met(
                    thread_id,
                    notify_thread.subject or "",
                    notify_thread.goal or "",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch goal_met notification for thread {thread_id}: {exc}")

    logger.info(f"Goal status for thread {thread_id}: {old_status} -> {status}")
    return True


async def clear_goal(thread_id: int, actor: str = "user") -> bool:
    """Remove goal from a thread."""
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return False
        thread.goal = None
        thread.acceptance_criteria = None
        thread.goal_status = None
        thread.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="goal_cleared",
        thread_id=thread_id,
        actor=actor,
    )
    return True


async def check_goal_met(thread_id: int) -> dict:
    """Use LLM to evaluate whether a thread's goal has been met. Returns {met: bool, reason: str}."""
    if not llm_available():
        return {"met": False, "reason": "LLM not available"}

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread or not thread.goal:
            return {"met": False, "reason": "No goal set"}

        # Get recent emails for context
        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.desc())
            .limit(10)
        )
        emails = result.scalars().all()

    email_summary = "\n".join([
        f"{'SENT' if e.is_sent else 'RECEIVED'} ({e.date}): {(e.body_plain or '')[:500]}"
        for e in reversed(emails)
    ])

    system = """You evaluate whether an email thread's goal has been met.
Respond with JSON: {"met": true/false, "reason": "brief explanation"}"""

    user_msg = f"""Goal: {thread.goal}
Acceptance Criteria: {thread.acceptance_criteria or 'None specified'}

Recent emails:
{email_summary}

Has the goal been met based on the email conversation?"""

    result = await complete_json(system, user_msg)
    met = result.get("met", False)

    if met:
        await update_goal_status(thread_id, "met", actor="system")

    return {"met": met, "reason": result.get("reason", "Unknown")}
