"""Triage engine — single entry point for agent decision-making."""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from sqlalchemy import select, func

from src.db.models import Thread, Draft, SecurityEvent, Email
from src.db.session import async_session

logger = logging.getLogger("ghostpost.engine.triage")


@dataclass
class TriageAction:
    action: str          # "approve_draft", "follow_up", "review_security", "review_new", "check_goal"
    target_type: str     # "draft", "thread", "security_event"
    target_id: int
    reason: str
    priority: str        # "critical", "high", "medium", "low"
    command: str         # Exact CLI command to execute
    score: int = 0       # Internal sorting score


@dataclass
class TriageSnapshot:
    timestamp: str
    summary: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    overdue_threads: list = field(default_factory=list)
    pending_drafts: list = field(default_factory=list)
    security_incidents: list = field(default_factory=list)
    new_threads: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


async def get_triage_data(limit: int = 10) -> TriageSnapshot:
    """Build a complete triage snapshot with prioritized actions."""
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        # Thread state counts
        state_rows = (await session.execute(
            select(Thread.state, func.count(Thread.id)).group_by(Thread.state)
        )).all()
        state_counts = {row[0]: row[1] for row in state_rows}
        total_threads = sum(state_counts.values())

        # Unread count
        unread = (await session.execute(
            select(func.count(Email.id)).where(Email.is_read == False)  # noqa: E712
        )).scalar() or 0

        # Pending drafts — oldest first so the agent clears the backlog in order
        draft_result = await session.execute(
            select(Draft).where(Draft.status == "pending").order_by(Draft.created_at.asc())
        )
        drafts = draft_result.scalars().all()

        # Security incidents awaiting resolution
        sec_result = await session.execute(
            select(SecurityEvent)
            .where(SecurityEvent.resolution == "pending")
            .order_by(SecurityEvent.timestamp.desc())
            .limit(20)
        )
        sec_events = sec_result.scalars().all()

        # Overdue follow-ups — threads where the deadline has passed
        overdue_result = await session.execute(
            select(Thread).where(
                Thread.state.in_(["WAITING_REPLY", "FOLLOW_UP"]),
                Thread.next_follow_up_date <= now,
            ).order_by(Thread.next_follow_up_date.asc())
        )
        overdue = overdue_result.scalars().all()

        # NEW threads that have not been triaged yet
        new_result = await session.execute(
            select(Thread)
            .where(Thread.state == "NEW")
            .order_by(Thread.last_activity_at.desc().nullslast())
            .limit(10)
        )
        new_threads = new_result.scalars().all()

        # ACTIVE threads with in-progress goals that may have been fulfilled
        goal_result = await session.execute(
            select(Thread).where(
                Thread.goal.isnot(None),
                Thread.goal_status == "in_progress",
                Thread.state == "ACTIVE",
            ).order_by(Thread.updated_at.desc().nullslast()).limit(5)
        )
        goal_threads = goal_result.scalars().all()

    # Build prioritized action list
    actions: list[TriageAction] = []

    # Security events — highest priority; block all agent action until resolved
    for ev in sec_events:
        if ev.severity == "critical":
            score = 100
        elif ev.severity == "high":
            score = 80
        else:
            score = 40
        thread_ref = f" on thread #{ev.thread_id}" if ev.thread_id else ""
        actions.append(TriageAction(
            action="review_security",
            target_type="security_event",
            target_id=ev.id,
            reason=f"{ev.severity.upper()} {ev.event_type}{thread_ref}",
            priority="critical" if ev.severity == "critical" else "high",
            command="ghostpost quarantine list --json",
            score=score,
        ))

    # Pending drafts — agent must approve or reject before they expire
    for draft in drafts:
        age_hours = (
            (now - draft.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if draft.created_at
            else 0
        )
        score = 60 if age_hours > 2 else 35
        subject = (draft.subject or "(no subject)")[:50]
        actions.append(TriageAction(
            action="approve_draft",
            target_type="draft",
            target_id=draft.id,
            reason=f"Draft pending {age_hours:.0f}h: {subject}",
            priority="high" if age_hours > 2 else "medium",
            command=f"ghostpost draft-approve {draft.id} --json",
            score=score,
        ))

    # Overdue threads — follow-up deadline has passed
    for thread in overdue:
        days_overdue = (
            (now - thread.next_follow_up_date.replace(tzinfo=timezone.utc)).days
            if thread.next_follow_up_date
            else 0
        )
        score = 50 if days_overdue > 3 else 30
        subject = (thread.subject or "(no subject)")[:50]
        actions.append(TriageAction(
            action="follow_up",
            target_type="thread",
            target_id=thread.id,
            reason=f"Overdue {days_overdue}d: {subject}",
            priority="high" if days_overdue > 3 else "medium",
            command=f'ghostpost reply {thread.id} --body "..." --json',
            score=score,
        ))

    # NEW threads — need initial triage; high-priority ones surfaced first
    for thread in new_threads:
        prio = thread.priority or "medium"
        score = 40 if prio in ("high", "critical") else 15
        subject = (thread.subject or "(no subject)")[:50]
        actions.append(TriageAction(
            action="review_new",
            target_type="thread",
            target_id=thread.id,
            reason=f"New thread [{prio}]: {subject}",
            priority="high" if prio in ("high", "critical") else "low",
            command=f"ghostpost brief {thread.id} --json",
            score=score,
        ))

    # In-progress goals — check whether the goal has been met
    for thread in goal_threads:
        goal_text = (thread.goal or "")[:40]
        actions.append(TriageAction(
            action="check_goal",
            target_type="thread",
            target_id=thread.id,
            reason=f"Goal may be met: {goal_text}",
            priority="low",
            command=f"ghostpost goal {thread.id} --check --json",
            score=20,
        ))

    # Sort by descending score and cap at limit
    actions.sort(key=lambda a: a.score, reverse=True)
    actions = actions[:limit]

    snapshot = TriageSnapshot(
        timestamp=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        summary={
            "total_threads": total_threads,
            "unread": unread,
            "by_state": state_counts,
            "pending_drafts": len(drafts),
            "security_incidents": len(sec_events),
            "overdue_threads": len(overdue),
            "new_threads": len(new_threads),
        },
        actions=[asdict(a) for a in actions],
        overdue_threads=[
            {
                "id": t.id,
                "subject": (t.subject or "")[:60],
                "days_overdue": (
                    (now - t.next_follow_up_date.replace(tzinfo=timezone.utc)).days
                    if t.next_follow_up_date
                    else 0
                ),
            }
            for t in overdue
        ],
        pending_drafts=[
            {
                "id": d.id,
                "thread_id": d.thread_id,
                "subject": (d.subject or "")[:60],
                "age_hours": round(
                    (now - d.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600,
                    1,
                ) if d.created_at else 0,
            }
            for d in drafts
        ],
        security_incidents=[
            {
                "id": e.id,
                "severity": e.severity,
                "event_type": e.event_type,
                "thread_id": e.thread_id,
            }
            for e in sec_events
        ],
        new_threads=[
            {
                "id": t.id,
                "subject": (t.subject or "")[:60],
                "priority": t.priority,
            }
            for t in new_threads
        ],
    )

    logger.info(
        "Triage: %d actions, %d overdue, %d drafts, %d security",
        len(actions),
        len(overdue),
        len(drafts),
        len(sec_events),
    )
    return snapshot
