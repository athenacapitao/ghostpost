"""Reply composer — generates reply text using LLM with reply_style setting."""

import logging

from sqlalchemy import select

from src.db.models import Contact, Email, Setting, Thread
from src.db.session import async_session
from src.engine.llm import complete, llm_available

logger = logging.getLogger("ghostpost.engine.composer")

STYLE_PROMPTS = {
    "professional": "Write in a professional, clear business tone. Be polite but direct.",
    "casual": "Write in a friendly, casual tone. Keep it warm and approachable.",
    "formal": "Write in a formal, respectful tone. Use proper salutations and sign-offs.",
    "custom": "",  # Will use the custom prompt from settings
}

DEFAULT_STYLE = "professional"


async def _get_reply_style() -> str:
    """Get the reply_style setting value."""
    async with async_session() as session:
        setting = await session.get(Setting, "reply_style")
        if setting and setting.value:
            return setting.value
    return DEFAULT_STYLE


async def _get_custom_style_prompt() -> str:
    """Get custom style prompt if reply_style is 'custom'."""
    async with async_session() as session:
        setting = await session.get(Setting, "reply_style_custom")
        if setting and setting.value:
            return setting.value
    return STYLE_PROMPTS["professional"]


async def generate_reply(
    thread_id: int,
    instructions: str | None = None,
    style_override: str | None = None,
) -> dict:
    """Generate a reply for a thread using LLM.

    Args:
        thread_id: The thread to reply to
        instructions: Optional specific instructions for this reply
        style_override: Override the default reply style for this reply

    Returns:
        {"body": str, "style": str, "subject": str, "to": str} or {"error": str}
    """
    if not llm_available():
        return {"error": "LLM not available"}

    # Get thread context
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return {"error": "Thread not found"}

        emails = (
            await session.execute(
                select(Email)
                .where(Email.thread_id == thread_id)
                .order_by(Email.date.asc().nullslast())
            )
        ).scalars().all()

        if not emails:
            return {"error": "No emails in thread"}

        last_email = emails[-1]
        recipient = last_email.from_address or ""

        # Try to get contact info
        contact = None
        if recipient:
            contact = (
                await session.execute(
                    select(Contact).where(Contact.email == recipient)
                )
            ).scalar_one_or_none()

    # Get style
    style = style_override or await _get_reply_style()
    if style == "custom":
        style_prompt = await _get_custom_style_prompt()
    else:
        style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["professional"])

    # Build conversation context (last 10 emails max to stay within token budget)
    conversation = []
    for email in emails[-10:]:
        direction = "SENT" if email.is_sent else "RECEIVED"
        body = (email.body_plain or "")[:1000]
        conversation.append(
            f"[{direction}] From: {email.from_address} ({email.date})\n{body}"
        )

    conv_text = "\n---\n".join(conversation)

    # Build contact context
    contact_context = ""
    if contact:
        contact_context = f"\nContact info: {contact.name or 'Unknown'}"
        if contact.preferred_style:
            contact_context += f", prefers {contact.preferred_style} communication"
        if contact.relationship_type and contact.relationship_type != "unknown":
            contact_context += f", relationship: {contact.relationship_type}"

    # Build system prompt
    system = f"""You are writing an email reply on behalf of Athena.
{style_prompt}

RULES:
- Write ONLY the reply body text — no subject line, no headers, no "From:" lines
- Do NOT include greeting lines like "Dear..." unless the style is formal
- Keep it concise and on-topic
- Match the language of the conversation (if they write in Portuguese, reply in Portuguese)
- Sign off with just "Athena" if appropriate for the style
{contact_context}"""

    # Build user message
    user_msg = f"Thread subject: {thread.subject}\n"
    if thread.goal:
        user_msg += f"Goal: {thread.goal}\n"
    if thread.playbook:
        user_msg += f"Active playbook: {thread.playbook}\n"
    if instructions:
        user_msg += f"\nSpecific instructions: {instructions}\n"
    user_msg += f"\nConversation:\n{conv_text}\n\nWrite a reply to the most recent email."

    try:
        body = await complete(system, user_msg, max_tokens=1024, temperature=0.4)
        body = body.strip()

        # Build subject with Re: prefix if not already present
        subject = last_email.subject or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        return {
            "body": body,
            "style": style,
            "subject": subject,
            "to": recipient,
        }
    except Exception as exc:
        logger.error("Failed to generate reply for thread %d: %s", thread_id, exc)
        return {"error": str(exc)}
