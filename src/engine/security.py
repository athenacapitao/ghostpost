"""Security scoring engine — rule-based 0-100 score per email.

Scoring factors (from SECURITY.md):
- Known sender: +30 (vs +0 for unknown)
- Previous threads with sender: +20 (vs +0 for first contact)
- No suspicious patterns: +20 (vs -30 for instruction-like language)
- No unknown links: +15 (vs -15 for links to unknown domains)
- Safe attachment types: +15 (vs -20 for risky types)
"""

import logging
import re

from sqlalchemy import select, update, func

from src.db.models import Attachment, Contact, Email, Thread
from src.db.session import async_session

logger = logging.getLogger("ghostpost.engine.security")

# Patterns that indicate prompt injection attempts
SUSPICIOUS_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"new\s+directive",
    r"SYSTEM\s*:",
    r"###\s*END\s+TASK\s*###",
    r"###\s*NEW\s+TASK\s*###",
    r"you\s+are\s+now\s+a",
    r"forget\s+everything",
    r"disregard\s+(all\s+)?prior",
    r"act\s+as\s+if",
    r"\[INST\]",
    r"<\|im_start\|>",
]

# Risky attachment types
RISKY_EXTENSIONS = {".exe", ".bat", ".scr", ".cmd", ".ps1", ".vbs", ".msi", ".dll", ".com", ".pif"}

# Known safe domains (will not flag links from these)
SAFE_DOMAINS = {
    "google.com", "gmail.com", "github.com", "linkedin.com", "notion.so",
    "todoist.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
    "slack.com", "zoom.us", "microsoft.com", "outlook.com", "apple.com",
    "dropbox.com", "drive.google.com", "docs.google.com", "youtube.com",
}


def _check_suspicious_patterns(text: str) -> bool:
    """Check if text contains prompt injection patterns."""
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _extract_domains(text: str) -> set[str]:
    """Extract domains from URLs in text."""
    urls = re.findall(r'https?://([^\s/>"\']+)', text)
    domains = set()
    for url in urls:
        # Get root domain (last 2 parts)
        parts = url.lower().split(".")
        if len(parts) >= 2:
            domains.add(".".join(parts[-2:]))
    return domains


def _has_risky_attachments(attachments: list[dict] | None) -> bool:
    """Check if any attachments have risky file types."""
    if not attachments:
        return False
    for att in attachments:
        filename = (att.get("filename") or "").lower()
        for ext in RISKY_EXTENSIONS:
            if filename.endswith(ext):
                return True
    return False


async def score_email(email_id: int) -> int | None:
    """Calculate security score for an email (0-100)."""
    async with async_session() as session:
        email = await session.get(Email, email_id)
        if not email:
            return None

        score = 0
        sender = email.from_address or ""

        # Factor 1: Known sender (+30)
        contact = (
            await session.execute(
                select(Contact).where(Contact.email == sender)
            )
        ).scalar_one_or_none()

        if contact:
            score += 30

            # Factor 2: Previous threads (+20 if > 1 thread)
            thread_count = (
                await session.execute(
                    select(func.count(Email.thread_id.distinct()))
                    .where(Email.from_address == sender)
                )
            ).scalar() or 0
            if thread_count > 1:
                score += 20
        # Unknown sender = +0

        # Factor 3: Suspicious patterns
        text = f"{email.subject or ''} {email.body_plain or ''} {email.body_html or ''}"
        if _check_suspicious_patterns(text):
            score -= 30
        else:
            score += 20

        # Factor 4: Links
        domains = _extract_domains(text)
        unknown_domains = domains - SAFE_DOMAINS
        if unknown_domains:
            score -= 15
        else:
            score += 15

        # Factor 5: Attachments
        attachments = email.attachment_metadata or []
        if _has_risky_attachments(attachments):
            score -= 20
        elif attachments:
            score += 10  # Has attachments but they're safe
        else:
            score += 15  # No attachments

        # Clamp to 0-100
        score = max(0, min(100, score))

        await session.execute(
            update(Email).where(Email.id == email_id).values(security_score=score)
        )
        await session.commit()
        logger.info(f"Email {email_id} security score: {score}")
        return score


async def update_thread_security_avg(thread_id: int) -> int | None:
    """Update thread's average security score from its emails."""
    async with async_session() as session:
        result = await session.execute(
            select(func.avg(Email.security_score))
            .where(Email.thread_id == thread_id)
            .where(Email.security_score.isnot(None))
        )
        avg = result.scalar()
        if avg is not None:
            avg_int = round(avg)
            await session.execute(
                update(Thread)
                .where(Thread.id == thread_id)
                .values(security_score_avg=avg_int)
            )
            await session.commit()
            return avg_int
    return None


async def score_all_unscored() -> dict:
    """Batch score all emails without a security score."""
    stats = {"emails_scored": 0, "threads_updated": 0}

    async with async_session() as session:
        result = await session.execute(
            select(Email.id).where(Email.security_score.is_(None))
        )
        email_ids = [row[0] for row in result.all()]

    logger.info(f"Scoring {len(email_ids)} emails")
    for eid in email_ids:
        s = await score_email(eid)
        if s is not None:
            stats["emails_scored"] += 1

    # Update thread averages
    async with async_session() as session:
        result = await session.execute(select(Thread.id))
        thread_ids = [row[0] for row in result.all()]

    for tid in thread_ids:
        r = await update_thread_security_avg(tid)
        if r is not None:
            stats["threads_updated"] += 1

    logger.info(f"Security scoring complete: {stats}")
    return stats
