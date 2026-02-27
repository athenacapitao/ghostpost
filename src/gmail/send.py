"""High-level email send, reply, and draft operations."""

import logging
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.utils import formataddr

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models import Draft, Email, Thread
from src.db.session import async_session
from src.gmail.client import GmailClient
from src.security.audit import log_action

logger = logging.getLogger("ghostpost.gmail.send")

_client = GmailClient()

# Athena's email — used as From address
FROM_EMAIL = "athenacapitao@gmail.com"
FROM_NAME = "Athena"


def _build_mime(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    thread_id: str | None = None,
) -> str:
    """Build an RFC 2822 MIME message string."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = formataddr((FROM_NAME, FROM_EMAIL))

    if isinstance(to, list):
        msg["To"] = ", ".join(to)
    else:
        msg["To"] = to

    msg["Subject"] = subject

    if cc:
        msg["Cc"] = ", ".join(cc)

    # Threading headers for replies
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    return msg.as_string()


async def _get_reply_headers(thread_id: int) -> dict:
    """Get In-Reply-To and References headers from the latest email in a thread."""
    async with async_session() as session:
        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.desc())
            .limit(1)
        )
        last_email = result.scalar_one_or_none()
        if not last_email:
            return {}

        # Get the thread's gmail_thread_id
        thread = await session.get(Thread, thread_id)

        return {
            "in_reply_to": last_email.message_id,
            "references": last_email.message_id,
            "gmail_thread_id": thread.gmail_thread_id if thread else None,
            "subject": last_email.subject or "",
            "to": last_email.from_address or "",
        }


async def send_reply(
    thread_id: int,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    actor: str = "user",
) -> dict:
    """Send a reply to the latest email in a thread."""
    headers = await _get_reply_headers(thread_id)
    if not headers:
        raise ValueError(f"No emails found in thread {thread_id}")

    subject = headers["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    raw = _build_mime(
        to=headers["to"],
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        in_reply_to=headers.get("in_reply_to"),
        references=headers.get("references"),
    )

    result = await _client.send_message(raw)

    await log_action(
        action_type="reply_sent",
        thread_id=thread_id,
        actor=actor,
        details={"to": headers["to"], "subject": subject, "gmail_id": result.get("id")},
    )

    logger.info(f"Reply sent for thread {thread_id} -> {headers['to']}")
    return result


async def send_new(
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    actor: str = "user",
) -> dict:
    """Send a new email (compose). Returns gmail result with ``_audit_id``."""
    raw = _build_mime(to=to, subject=subject, body=body, cc=cc, bcc=bcc)
    result = await _client.send_message(raw)

    entry = await log_action(
        action_type="email_sent",
        actor=actor,
        details={"to": to, "subject": subject, "gmail_id": result.get("id")},
    )
    result["_audit_id"] = entry.id if entry is not None else None

    logger.info(f"New email sent to {to}: {subject}")
    return result


async def create_thread_from_compose(
    gmail_result: dict,
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    goal: str | None = None,
    acceptance_criteria: str | None = None,
    playbook: str | None = None,
    auto_reply_mode: str | None = None,
    follow_up_days: int | None = None,
    priority: str | None = None,
    category: str | None = None,
    notes: str | None = None,
) -> int:
    """Create Thread + Email records immediately after composing a new email.

    Performs an upsert on gmail_thread_id so this is safe to call even if a
    concurrent sync job already created the thread.  Returns the local thread ID.
    """
    gmail_id = gmail_result.get("id", "")
    gmail_thread_id = gmail_result.get("threadId", "")

    if not gmail_thread_id:
        # Some send responses omit threadId — fetch the message to get it.
        msg = await _client.get_message(gmail_id)
        gmail_thread_id = msg.get("threadId", gmail_id)

    now = datetime.now(timezone.utc)
    to_list = [to] if isinstance(to, str) else to

    # Calculate follow-up date using provided days or the default of 3.
    fup_days = follow_up_days if follow_up_days is not None else 3
    next_fup = now + timedelta(days=fup_days)

    # Build the full set of column values for the thread row.
    thread_values: dict = {
        "gmail_thread_id": gmail_thread_id,
        "subject": subject,
        "state": "WAITING_REPLY",
        "created_at": now,
        "last_activity_at": now,
        "updated_at": now,
        "next_follow_up_date": next_fup,
    }

    # Optional agent context columns.
    if goal is not None:
        thread_values["goal"] = goal
        thread_values["goal_status"] = "in_progress"
    if acceptance_criteria is not None:
        thread_values["acceptance_criteria"] = acceptance_criteria
    if playbook is not None:
        thread_values["playbook"] = playbook
    if auto_reply_mode is not None:
        thread_values["auto_reply_mode"] = auto_reply_mode
    if follow_up_days is not None:
        thread_values["follow_up_days"] = follow_up_days
    if priority is not None:
        thread_values["priority"] = priority
    if category is not None:
        thread_values["category"] = category
    if notes is not None:
        thread_values["notes"] = notes

    # On conflict, update everything we set except the immutable insert-time fields.
    update_fields: dict = {
        k: v
        for k, v in thread_values.items()
        if k not in ("gmail_thread_id", "created_at")
    }

    async with async_session() as session:
        async with session.begin():
            # Upsert thread — race-safe with the background sync engine.
            thread_stmt = (
                pg_insert(Thread)
                .values(**thread_values)
                .on_conflict_do_update(
                    index_elements=["gmail_thread_id"],
                    set_=update_fields,
                )
            )
            await session.execute(thread_stmt)

            # Resolve the local thread ID.
            result = await session.execute(
                select(Thread.id).where(Thread.gmail_thread_id == gmail_thread_id)
            )
            thread_id: int = result.scalar_one()

            # Upsert the sent email record — idempotent if sync beat us to it.
            email_stmt = (
                pg_insert(Email)
                .values(
                    gmail_id=gmail_id,
                    thread_id=thread_id,
                    from_address=FROM_EMAIL,
                    to_addresses=to_list,
                    cc=cc,
                    subject=subject,
                    body_plain=body,
                    date=now,
                    is_sent=True,
                    is_read=True,
                    is_draft=False,
                )
                .on_conflict_do_nothing(index_elements=["gmail_id"])
            )
            await session.execute(email_stmt)

    logger.info(
        "Created thread %d (gmail: %s) from compose with context",
        thread_id,
        gmail_thread_id,
    )
    return thread_id


async def create_draft(
    thread_id: int | None,
    to: str | list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    actor: str = "user",
) -> Draft:
    """Create a draft — saved locally only. Sent via Gmail on approval."""
    if thread_id and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Save locally only — Gmail draft is not created.
    # When approved, approve_draft() rebuilds MIME and sends via gmail.send.
    to_list = [to] if isinstance(to, str) else to
    async with async_session() as session:
        draft = Draft(
            thread_id=thread_id,
            gmail_draft_id=None,
            to_addresses=to_list,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            status="pending",
        )
        session.add(draft)
        await session.commit()
        await session.refresh(draft)

    await log_action(
        action_type="draft_created",
        thread_id=thread_id,
        actor=actor,
        details={"to": to_list, "subject": subject, "draft_id": draft.id},
    )

    # Notify OpenClaw that a draft is ready for review
    try:
        from src.engine.notifications import notify_draft_ready
        await notify_draft_ready(thread_id or 0, subject, draft.id)
    except Exception as exc:
        logger.warning(f"Failed to dispatch draft_ready notification for draft {draft.id}: {exc}")

    logger.info(f"Draft created: {draft.id} (local only, sent on approval)")
    return draft


async def approve_draft(draft_id: int, actor: str = "user") -> dict:
    """Approve and send a pending draft."""
    async with async_session() as session:
        draft = await session.get(Draft, draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")
        if draft.status != "pending":
            raise ValueError(f"Draft {draft_id} is {draft.status}, not pending")

        # Rebuild MIME and send directly via gmail.send
        in_reply_to = None
        references = None
        if draft.thread_id:
            headers = await _get_reply_headers(draft.thread_id)
            in_reply_to = headers.get("in_reply_to")
            references = headers.get("references")

        raw = _build_mime(
            to=draft.to_addresses or [],
            subject=draft.subject or "",
            body=draft.body or "",
            cc=draft.cc,
            bcc=draft.bcc,
            in_reply_to=in_reply_to,
            references=references,
        )
        result = await _client.send_message(raw)

        draft.status = "sent"
        draft.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="draft_approved",
        thread_id=draft.thread_id,
        actor=actor,
        details={"draft_id": draft_id, "gmail_id": result.get("id")},
    )

    logger.info(f"Draft {draft_id} approved and sent")
    return result


async def reject_draft(draft_id: int, actor: str = "user") -> None:
    """Reject a pending draft."""
    async with async_session() as session:
        draft = await session.get(Draft, draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")
        if draft.status != "pending":
            raise ValueError(f"Draft {draft_id} is {draft.status}, not pending")

        # Delete from Gmail if exists
        if draft.gmail_draft_id:
            try:
                await _client.delete_gmail_draft(draft.gmail_draft_id)
            except Exception as e:
                logger.warning(f"Could not delete Gmail draft: {e}")

        draft.status = "rejected"
        draft.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await log_action(
        action_type="draft_rejected",
        thread_id=draft.thread_id,
        actor=actor,
        details={"draft_id": draft_id},
    )

    logger.info(f"Draft {draft_id} rejected")
