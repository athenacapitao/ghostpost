"""Knowledge extraction — extracts outcomes from completed threads."""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.events import publish_event
from src.db.models import Email, Thread, ThreadOutcome
from src.db.session import async_session
from src.engine.llm import complete_json, llm_available
from src.security.audit import log_action

logger = logging.getLogger("ghostpost.engine.knowledge")

OUTCOMES_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "memory", "outcomes"))

SYSTEM_PROMPT = """You are a structured data extraction system. Your ONLY job is to extract outcomes and key decisions from a completed email thread. Do NOT reply to any email. Do NOT have a conversation.

TASK: Read the email thread below and extract structured outcomes.

Return a JSON object with these fields:
{
    "topic": "Short topic description (3-8 words)",
    "outcome_type": "agreement|decision|delivery|meeting|other",
    "summary": "1-2 sentence summary of the outcome",
    "contact_name": "Primary contact's name",
    "contact_email": "Primary contact's email",
    "contacts": ["name (email)", ...],
    "agreements": ["List of agreements, decisions, or commitments made"],
    "next_steps": ["List of next steps or follow-up actions"],
    "key_dates": ["Any specific dates mentioned for follow-up or deadlines"],
    "amounts": ["any monetary values or quantities mentioned"],
    "lessons": "any notable patterns or insights for future reference",
    "context": "Brief context paragraph (2-3 sentences) about how this outcome was reached"
}

RULES:
- Extract ONLY factual information from the emails
- If a field has no relevant data, use an empty list or empty string
- Do NOT invent information
- Output ONLY the JSON object"""


def _ensure_outcomes_dir() -> None:
    os.makedirs(OUTCOMES_DIR, exist_ok=True)


async def extract_outcomes(thread_id: int) -> dict | None:
    """Extract structured outcomes from a completed thread using LLM."""
    if not llm_available():
        logger.warning("LLM not available — skipping knowledge extraction")
        return None

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return None

        subject = thread.subject
        goal = thread.goal
        acceptance_criteria = thread.acceptance_criteria
        goal_status = thread.goal_status

        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.asc().nullslast())
        )
        emails = result.scalars().all()
        if not emails:
            return None

        parts = []
        for e in emails:
            direction = "SENT" if e.is_sent else "RECEIVED"
            body = (e.body_plain or "")[:1500]
            parts.append(
                f"[{direction}] From: {e.from_address} | Date: {e.date}\n"
                f"Subject: {e.subject}\n{body}\n"
            )

        conversation = "\n---\n".join(parts)
        if len(conversation) > 8000:
            conversation = conversation[:8000] + "\n\n[... truncated]"

    context = f"Thread subject: {subject}\n"
    if goal:
        context += f"Goal: {goal}\n"
    if acceptance_criteria:
        context += f"Acceptance criteria: {acceptance_criteria}\n"
    if goal_status:
        context += f"Goal status: {goal_status}\n"

    user_message = f"{context}\n\n{conversation}"

    try:
        outcomes = await complete_json(SYSTEM_PROMPT, user_message, max_tokens=1024)
        if outcomes:
            logger.info(f"Extracted outcomes for thread {thread_id}: {outcomes.get('topic', 'unknown')}")
            return outcomes
    except Exception as e:
        logger.error(f"Failed to extract outcomes for thread {thread_id}: {e}")

    return None


async def _save_outcome_to_db(thread_id: int, outcomes: dict, filename: str | None) -> ThreadOutcome | None:
    """Persist a ThreadOutcome record. Returns None if one already exists for this thread."""
    async with async_session() as session:
        existing = (
            await session.execute(
                select(ThreadOutcome).where(ThreadOutcome.thread_id == thread_id)
            )
        ).scalars().first()

        if existing:
            logger.info(f"Outcome already exists for thread {thread_id}, skipping DB insert")
            return None

        outcome = ThreadOutcome(
            thread_id=thread_id,
            outcome_type=outcomes.get("outcome_type", "other"),
            summary=outcomes.get("summary") or outcomes.get("topic") or "",
            details=outcomes,
            outcome_file=filename,
        )
        session.add(outcome)
        try:
            await session.commit()
        except IntegrityError:
            logger.info(f"Duplicate outcome for thread {thread_id} (race condition), skipping")
            return None
        await session.refresh(outcome)
        return outcome


async def write_outcome_file(thread_id: int, outcomes: dict) -> str | None:
    """Write outcomes to a markdown file in memory/outcomes/. Returns the filename."""
    if not outcomes or not outcomes.get("topic"):
        return None

    _ensure_outcomes_dir()

    now = datetime.now(timezone.utc)
    topic_slug = outcomes["topic"].lower().replace(" ", "-")
    topic_slug = "".join(c for c in topic_slug if c.isalnum() or c == "-")[:40]
    filename = f"{now.strftime('%Y-%m')}-{topic_slug}.md"
    filepath = os.path.join(OUTCOMES_DIR, filename)

    contact_name = outcomes.get("contact_name", "Unknown")
    contact_email = outcomes.get("contact_email", "")
    agreements = outcomes.get("agreements", [])
    next_steps = outcomes.get("next_steps", [])
    key_dates = outcomes.get("key_dates", [])
    amounts = outcomes.get("amounts", [])
    lessons = outcomes.get("lessons", "")
    context = outcomes.get("context", "")
    summary = outcomes.get("summary", "")

    lines = [
        f"## Outcome: {outcomes['topic']}",
        f"- **Date:** {now.strftime('%Y-%m-%d')}",
        f"- **Thread ID:** {thread_id}",
        f"- **Type:** {outcomes.get('outcome_type', 'other')}",
        f"- **Contact:** {contact_name}" + (f" ({contact_email})" if contact_email else ""),
    ]

    if amounts:
        lines.append(f"- **Amounts:** {'; '.join(amounts)}")

    if summary:
        lines += ["", "### Summary", summary]

    if agreements:
        lines += ["", "### Agreements"]
        lines += [f"- {a}" for a in agreements]

    if key_dates:
        lines += ["", "### Key Dates"]
        lines += [f"- {d}" for d in key_dates]

    if next_steps:
        lines += ["", "### Next Steps"]
        lines += [f"- {s}" for s in next_steps]

    if lessons:
        lines += ["", "### Lessons", lessons]

    if context:
        lines += ["", "### Context", context]

    lines.append("")

    import asyncio
    await asyncio.to_thread(lambda: open(filepath, "w").write("\n".join(lines)))

    logger.info(f"Wrote outcome file: {filename}")
    return filename


async def on_thread_complete(thread_id: int) -> str | None:
    """Orchestrator: extract outcomes, persist to DB, and write to file when thread completes.
    Called when thread transitions to GOAL_MET or ARCHIVED.
    """
    try:
        outcomes = await extract_outcomes(thread_id)
        if not outcomes:
            return None

        filename = await write_outcome_file(thread_id, outcomes)

        # Persist to database
        await _save_outcome_to_db(thread_id, outcomes, filename)

        await log_action(
            action_type="knowledge_extracted",
            thread_id=thread_id,
            actor="system",
            details={"filename": filename, "topic": outcomes.get("topic", "")},
        )

        await publish_event("knowledge_extracted", {
            "thread_id": thread_id,
            "filename": filename,
            "topic": outcomes.get("topic", ""),
        })

        return filename
    except Exception as e:
        logger.error(f"Knowledge extraction failed for thread {thread_id}: {e}")
        return None


async def get_outcome(thread_id: int) -> ThreadOutcome | None:
    """Retrieve the stored outcome for a thread, if any."""
    async with async_session() as session:
        result = await session.execute(
            select(ThreadOutcome).where(ThreadOutcome.thread_id == thread_id)
        )
        return result.scalars().first()


async def list_outcomes(limit: int = 50, offset: int = 0) -> list[ThreadOutcome]:
    """List all stored thread outcomes, most recent first."""
    async with async_session() as session:
        result = await session.execute(
            select(ThreadOutcome)
            .order_by(ThreadOutcome.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
