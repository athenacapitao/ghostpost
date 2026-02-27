"""Thread categorization — assigns freeform category based on first email."""

import logging

from sqlalchemy import select, update

from src.db.models import Email, Thread
from src.db.session import async_session
from src.engine.llm import complete_json, llm_available

logger = logging.getLogger("ghostpost.engine.categorizer")

SYSTEM_PROMPT = """You are a structured data extraction system. Your ONLY job is to read an email and output a JSON object. Do NOT reply to the email. Do NOT have a conversation. Do NOT add commentary.

TASK: Read the email below and assign a short category label (1-3 words).

Example categories: "Business Outreach", "Account Notification", "Personal", "Newsletter", "Project Update", "Service Alert", "Social Media", "Security Alert", "Financial"

OUTPUT FORMAT (JSON only, nothing else):
{"category": "Your Category Label"}

CRITICAL: Output ONLY the JSON object. No text before or after it. No markdown. No explanation."""


async def categorize_thread(thread_id: int) -> str | None:
    """Categorize a single thread based on its first email."""
    if not llm_available():
        return None

    async with async_session() as session:
        # Get first email in thread
        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.asc().nullslast())
            .limit(1)
        )
        email = result.scalar_one_or_none()
        if not email:
            return None

        body = (email.body_plain or "")[:2000]
        user_msg = f"EMAIL TO ANALYZE (do not reply to it):\n\nSubject: {email.subject or '(no subject)'}\n\nBody:\n{body}"

        try:
            data = await complete_json(SYSTEM_PROMPT, user_msg, max_tokens=100)
            category = data.get("category")
            if category:
                await session.execute(
                    update(Thread)
                    .where(Thread.id == thread_id)
                    .values(category=category)
                )
                await session.commit()
                logger.info(f"Thread {thread_id} categorized as: {category}")
                return category
        except Exception as e:
            logger.error(f"Failed to categorize thread {thread_id}: {e}")

    return None


async def categorize_all_uncategorized() -> int:
    """Batch categorize all threads without a category."""
    if not llm_available():
        logger.warning("LLM not available — skipping categorization")
        return 0

    async with async_session() as session:
        result = await session.execute(
            select(Thread.id).where(Thread.category.is_(None))
        )
        thread_ids = [row[0] for row in result.all()]

    logger.info(f"Categorizing {len(thread_ids)} uncategorized threads")
    count = 0
    for tid in thread_ids:
        cat = await categorize_thread(tid)
        if cat:
            count += 1

    logger.info(f"Categorized {count}/{len(thread_ids)} threads")
    return count
