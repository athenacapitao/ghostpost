"""Email analysis — sentiment, urgency, action_required per email. Priority per thread."""

import logging

from sqlalchemy import select, update, func

from src.db.models import Email, Thread
from src.db.session import async_session
from src.engine.llm import complete_json, llm_available

logger = logging.getLogger("ghostpost.engine.analyzer")

EMAIL_ANALYSIS_PROMPT = """You are a structured data extraction system. Your ONLY job is to analyze an email and output a JSON object. Do NOT reply to the email. Do NOT have a conversation. Do NOT add commentary.

TASK: Analyze the email below and extract these fields:
- sentiment: one of "positive", "neutral", "negative", "frustrated"
- urgency: one of "low", "medium", "high", "critical"
- action_required: object with "required" (boolean) and "description" (string or null)

OUTPUT FORMAT (JSON only, nothing else):
{"sentiment": "neutral", "urgency": "low", "action_required": {"required": false, "description": null}}

CRITICAL: Output ONLY the JSON object. No text before or after it. No markdown. No explanation."""

PRIORITY_PROMPT = """You are a structured data extraction system. Your ONLY job is to score thread priority and output a JSON object. Do NOT reply to any email. Do NOT have a conversation.

TASK: Given the thread info below, assign a priority level:
- "critical": Urgent deadline, legal/financial matter, VIP sender
- "high": Time-sensitive, important business, needs response soon
- "medium": Normal business correspondence
- "low": Newsletters, notifications, automated emails, social media

OUTPUT FORMAT (JSON only, nothing else):
{"priority": "medium"}

CRITICAL: Output ONLY the JSON object. No text before or after it. No markdown. No explanation."""


async def analyze_email(email_id: int) -> dict | None:
    """Analyze a single email for sentiment, urgency, action_required."""
    if not llm_available():
        return None

    async with async_session() as session:
        email = await session.get(Email, email_id)
        if not email:
            return None

        body = (email.body_plain or "")[:2000]
        user_msg = (
            f"EMAIL TO ANALYZE (do not reply to it):\n\n"
            f"From: {email.from_address}\n"
            f"Subject: {email.subject or '(no subject)'}\n"
            f"Date: {email.date}\n\n"
            f"Body:\n{body}"
        )

        try:
            data = await complete_json(EMAIL_ANALYSIS_PROMPT, user_msg, max_tokens=200)
            if not data:
                return None

            updates = {}
            if "sentiment" in data:
                updates["sentiment"] = data["sentiment"]
            if "urgency" in data:
                updates["urgency"] = data["urgency"]
            if "action_required" in data:
                updates["action_required"] = data["action_required"]

            if updates:
                await session.execute(
                    update(Email).where(Email.id == email_id).values(**updates)
                )
                await session.commit()
                logger.info(f"Email {email_id} analyzed: {data}")
                return data
        except Exception as e:
            logger.error(f"Failed to analyze email {email_id}: {e}")

    return None


async def score_thread_priority(thread_id: int) -> str | None:
    """Score thread priority based on its emails' analysis."""
    if not llm_available():
        return None

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return None

        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.desc().nullslast())
            .limit(5)
        )
        emails = result.scalars().all()

        # Build context for priority scoring
        email_info = []
        for e in emails:
            email_info.append(
                f"- From: {e.from_address}, "
                f"Sentiment: {e.sentiment or 'unknown'}, "
                f"Urgency: {e.urgency or 'unknown'}, "
                f"Action: {e.action_required}"
            )

        user_msg = (
            f"Thread Subject: {thread.subject}\n"
            f"Category: {thread.category or 'uncategorized'}\n"
            f"Summary: {thread.summary or 'no summary'}\n"
            f"Email count: {len(emails)}\n\n"
            f"Recent emails:\n" + "\n".join(email_info)
        )

        try:
            data = await complete_json(PRIORITY_PROMPT, user_msg, max_tokens=50)
            priority = data.get("priority")
            if priority:
                await session.execute(
                    update(Thread)
                    .where(Thread.id == thread_id)
                    .values(priority=priority)
                )
                await session.commit()
                logger.info(f"Thread {thread_id} priority: {priority}")
                return priority
        except Exception as e:
            logger.error(f"Failed to score priority for thread {thread_id}: {e}")

    return None


async def analyze_all_unanalyzed() -> dict:
    """Batch analyze all emails without sentiment and score all threads without priority."""
    if not llm_available():
        return {"emails_analyzed": 0, "threads_prioritized": 0}

    stats = {"emails_analyzed": 0, "threads_prioritized": 0}

    async with async_session() as session:
        # Emails without sentiment
        result = await session.execute(
            select(Email.id).where(Email.sentiment.is_(None))
        )
        email_ids = [row[0] for row in result.all()]

    logger.info(f"Analyzing {len(email_ids)} emails")
    for eid in email_ids:
        r = await analyze_email(eid)
        if r:
            stats["emails_analyzed"] += 1

    # Threads without priority
    async with async_session() as session:
        result = await session.execute(
            select(Thread.id).where(Thread.priority.is_(None))
        )
        thread_ids = [row[0] for row in result.all()]

    logger.info(f"Scoring priority for {len(thread_ids)} threads")
    for tid in thread_ids:
        r = await score_thread_priority(tid)
        if r:
            stats["threads_prioritized"] += 1

    logger.info(f"Analysis complete: {stats}")
    return stats
