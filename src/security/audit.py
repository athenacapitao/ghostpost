"""Audit logging and security event recording."""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from src.db.models import AuditLog, SecurityEvent
from src.db.session import async_session
from src.api.events import publish_event

logger = logging.getLogger("ghostpost.security.audit")


async def log_action(
    action_type: str,
    thread_id: int | None = None,
    email_id: int | None = None,
    actor: str = "system",
    details: dict | None = None,
) -> AuditLog:
    """Write an audit log entry and publish a WebSocket event."""
    async with async_session() as session:
        entry = AuditLog(
            action_type=action_type,
            thread_id=thread_id,
            email_id=email_id,
            actor=actor,
            details=details or {},
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

    await publish_event("audit", {
        "id": entry.id,
        "action_type": action_type,
        "thread_id": thread_id,
        "email_id": email_id,
        "actor": actor,
        "details": details or {},
    })

    logger.info(f"Audit: {action_type} by {actor} (thread={thread_id}, email={email_id})")
    return entry


async def log_security_event(
    event_type: str,
    severity: str,
    email_id: int | None = None,
    thread_id: int | None = None,
    details: dict | None = None,
    quarantined: bool = False,
) -> SecurityEvent:
    """Write a security event and publish a WebSocket alert."""
    async with async_session() as session:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            email_id=email_id,
            thread_id=thread_id,
            details=details or {},
            resolution="pending" if quarantined else None,
            quarantined=quarantined,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

    await publish_event("security_alert", {
        "id": event.id,
        "event_type": event_type,
        "severity": severity,
        "email_id": email_id,
        "thread_id": thread_id,
        "quarantined": quarantined,
    })

    logger.warning(f"Security: {event_type} [{severity}] (email={email_id}, quarantined={quarantined})")
    return event


async def update_audit_thread_id(audit_id: int, thread_id: int) -> None:
    """Backfill thread_id on an audit entry (e.g. after thread creation)."""
    async with async_session() as session:
        entry = await session.get(AuditLog, audit_id)
        if entry and entry.thread_id is None:
            entry.thread_id = thread_id
            await session.commit()


async def get_recent_actions(hours: int = 24, limit: int = 50) -> list[AuditLog]:
    """Get recent audit log entries."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    async with async_session() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.timestamp >= since)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_security_events(
    pending_only: bool = False,
    limit: int = 50,
) -> list[SecurityEvent]:
    """Get security events, optionally only pending/quarantined ones."""
    async with async_session() as session:
        q = select(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).limit(limit)
        if pending_only:
            q = q.where(SecurityEvent.resolution == "pending")
        result = await session.execute(q)
        return list(result.scalars().all())
