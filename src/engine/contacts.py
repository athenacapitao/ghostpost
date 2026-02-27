"""Contact profile builder — enriches contacts from email history."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update, func

from src.db.models import Contact, Email
from src.db.session import async_session
from src.engine.llm import complete_json, llm_available

logger = logging.getLogger("ghostpost.engine.contacts")

PROFILE_PROMPT = """You are a structured data extraction system. Your ONLY job is to analyze email history and output a JSON profile. Do NOT reply to any email. Do NOT have a conversation. Do NOT add commentary.

TASK: Given a contact's email history, extract:
- relationship_type: one of "client", "vendor", "friend", "colleague", "service", "unknown"
- communication_frequency: one of "daily", "weekly", "monthly", "rare"
- preferred_style: one of "brief", "detailed", "formal", "casual"
- topics: list of 1-5 topic keywords

Be conservative — if unsure, use "unknown".

OUTPUT FORMAT (JSON only, nothing else):
{"relationship_type": "colleague", "communication_frequency": "weekly", "preferred_style": "formal", "topics": ["project updates", "scheduling"]}

CRITICAL: Output ONLY the JSON object. No text before or after it. No markdown. No explanation."""


async def enrich_contact(contact_id: int) -> dict | None:
    """Enrich a contact's profile from their email history."""
    if not llm_available():
        return None

    async with async_session() as session:
        contact = await session.get(Contact, contact_id)
        if not contact:
            return None

        # Get emails from/to this contact
        result = await session.execute(
            select(Email)
            .where(Email.from_address == contact.email)
            .order_by(Email.date.desc().nullslast())
            .limit(20)
        )
        emails = result.scalars().all()
        if not emails:
            return None

        # Build email history summary
        lines = []
        for e in emails:
            snippet = (e.body_plain or "")[:200]
            lines.append(f"- [{e.date}] Subject: {e.subject or '(none)'} | {snippet}")

        user_msg = (
            f"CONTACT DATA TO ANALYZE (do not reply to any emails):\n\n"
            f"Contact: {contact.name or 'Unknown'} <{contact.email}>\n"
            f"Total emails from this contact: {len(emails)}\n\n"
            f"Email history (most recent first):\n" + "\n".join(lines)
        )

        try:
            data = await complete_json(PROFILE_PROMPT, user_msg, max_tokens=200)
            if not data:
                return None

            updates = {"enrichment_source": "email_history", "updated_at": datetime.now(timezone.utc)}
            if "relationship_type" in data:
                updates["relationship_type"] = data["relationship_type"]
            if "communication_frequency" in data:
                updates["communication_frequency"] = data["communication_frequency"]
            if "preferred_style" in data:
                updates["preferred_style"] = data["preferred_style"]
            if "topics" in data:
                updates["topics"] = data["topics"]

            await session.execute(
                update(Contact).where(Contact.id == contact_id).values(**updates)
            )
            await session.commit()
            logger.info(f"Contact {contact.email} enriched: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to enrich contact {contact_id}: {e}")

    return None


WEB_ENRICHMENT_PROMPT = """You are a contact intelligence system. Given a contact's name and email address, provide any publicly available information you can infer.

TASK: Based on the name and email domain, provide:
- company: the company/organization (from email domain)
- role: likely role or title if inferrable
- industry: industry of the company
- company_size: rough company size if known (startup/small/medium/large/enterprise)
- location: likely location/country if inferrable
- linkedin_likely: true if this person likely has a LinkedIn profile
- notes: any other relevant context about the company/domain

Be conservative — if you cannot infer something with reasonable confidence, use null.

OUTPUT FORMAT (JSON only):
{"company": "Acme Corp", "role": null, "industry": "Technology", "company_size": "medium", "location": "US", "linkedin_likely": true, "notes": "acme.com is a well-known tech company"}

CRITICAL: Output ONLY the JSON object."""


async def enrich_contact_web(contact_id: int) -> dict | None:
    """Enrich a contact using LLM knowledge about public information (name + email domain)."""
    if not llm_available():
        return None

    async with async_session() as session:
        contact = await session.get(Contact, contact_id)
        if not contact:
            return None

        name = contact.name or "Unknown"
        email = contact.email

    # Extract domain for context
    domain = email.split("@")[-1] if "@" in email else ""

    user_msg = (
        f"CONTACT TO RESEARCH:\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Domain: {domain}\n"
    )

    try:
        data = await complete_json(WEB_ENRICHMENT_PROMPT, user_msg, max_tokens=300)
        if not data:
            return None

        # Merge web data into contact notes (don't overwrite email-history enrichment)
        web_info = []
        if data.get("company"):
            web_info.append(f"Company: {data['company']}")
        if data.get("role"):
            web_info.append(f"Role: {data['role']}")
        if data.get("industry"):
            web_info.append(f"Industry: {data['industry']}")
        if data.get("location"):
            web_info.append(f"Location: {data['location']}")
        if data.get("company_size"):
            web_info.append(f"Company size: {data['company_size']}")

        if web_info:
            web_note = "Web enrichment: " + " | ".join(web_info)
            async with async_session() as session:
                contact = await session.get(Contact, contact_id)
                if contact:
                    existing_notes = contact.notes or ""
                    if "Web enrichment:" not in existing_notes:
                        contact.notes = (existing_notes + "\n" + web_note).strip()
                    contact.enrichment_source = (
                        "email_history+web" if contact.enrichment_source == "email_history"
                        else "web"
                    )
                    contact.updated_at = datetime.now(timezone.utc)
                    await session.commit()

        logger.info(f"Web enrichment for {email}: {data}")
        return data
    except Exception as e:
        logger.error(f"Web enrichment failed for contact {contact_id}: {e}")
        return None


async def enrich_all_unenriched() -> int:
    """Batch enrich contacts without enrichment_source."""
    if not llm_available():
        return 0

    async with async_session() as session:
        result = await session.execute(
            select(Contact.id).where(Contact.enrichment_source.is_(None))
        )
        contact_ids = [row[0] for row in result.all()]

    logger.info(f"Enriching {len(contact_ids)} contacts")
    count = 0
    for cid in contact_ids:
        r = await enrich_contact(cid)
        if r:
            count += 1

    logger.info(f"Enriched {count}/{len(contact_ids)} contacts")
    return count
