"""Thread summary generation — updated on each new email."""

import logging

from sqlalchemy import select, update

from src.db.models import Email, Thread
from src.db.session import async_session
from src.engine.llm import complete, llm_available

logger = logging.getLogger("ghostpost.engine.summarizer")

SYSTEM_PROMPT = """You are a structured data extraction system. Your ONLY job is to read email threads and produce a brief summary. Do NOT reply to any email. Do NOT have a conversation. Do NOT add greetings or commentary.

TASK: Read the email thread below and write a factual 2-4 sentence summary covering:
- What the thread is about
- Current status (who is waiting on whom)
- Key decisions or outcomes

RULES:
- Write in third person
- Be factual and concise
- No bullet points, just flowing text
- Output ONLY the summary text, nothing else
- Do NOT respond to or engage with the email content"""


async def summarize_thread(thread_id: int) -> str | None:
    """Generate or update summary for a thread."""
    if not llm_available():
        return None

    async with async_session() as session:
        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.asc().nullslast())
        )
        emails = result.scalars().all()
        if not emails:
            return None

        # Build conversation text
        parts = []
        for e in emails:
            direction = "SENT" if e.is_sent else "RECEIVED"
            body = (e.body_plain or "")[:1500]
            parts.append(
                f"[{direction}] From: {e.from_address} | Date: {e.date}\n"
                f"Subject: {e.subject}\n{body}\n"
            )

        conversation = "\n---\n".join(parts)
        # Truncate if very long
        if len(conversation) > 8000:
            conversation = conversation[:8000] + "\n\n[... truncated]"

        try:
            summary = await complete(SYSTEM_PROMPT, conversation, max_tokens=300)
            summary = summary.strip()
            if summary:
                await session.execute(
                    update(Thread)
                    .where(Thread.id == thread_id)
                    .values(summary=summary)
                )
                await session.commit()
                logger.info(f"Thread {thread_id} summarized ({len(summary)} chars)")
                return summary
        except Exception as e:
            logger.error(f"Failed to summarize thread {thread_id}: {e}")

    return None


async def summarize_all_unsummarized() -> int:
    """Batch summarize all threads without a summary."""
    if not llm_available():
        return 0

    async with async_session() as session:
        result = await session.execute(
            select(Thread.id).where(Thread.summary.is_(None))
        )
        thread_ids = [row[0] for row in result.all()]

    logger.info(f"Summarizing {len(thread_ids)} threads")
    count = 0
    for tid in thread_ids:
        s = await summarize_thread(tid)
        if s:
            count += 1

    logger.info(f"Summarized {count}/{len(thread_ids)} threads")
    return count
