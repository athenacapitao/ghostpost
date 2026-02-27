"""Structured thread brief generation for agent consumption."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from src.db.models import Contact, Email, Thread
from src.db.session import async_session

logger = logging.getLogger("ghostpost.engine.brief")


# Mapping from thread state to a plain-English action description.
_STATE_ACTION_LABELS: dict[str, str] = {
    "NEW": "Triage this thread — it has not been acted on yet",
    "ACTIVE": "This thread is active — monitor and respond as needed",
    "WAITING_REPLY": "Wait for reply (WAITING_REPLY state)",
    "FOLLOW_UP": "Send a follow-up — the deadline has passed with no reply",
    "GOAL_MET": "Goal has been met — no further action required",
    "ARCHIVED": "Thread is archived — no action needed",
}

# Mapping from auto_reply_mode to a human-readable instruction.
_AUTO_REPLY_LABELS: dict[str, str] = {
    "off": "Do not send replies automatically — notify user instead",
    "draft": "Create draft for approval before sending",
    "auto": "Send replies automatically without approval",
}


def _build_agent_instructions(thread: Thread) -> str:
    """Build the ## Agent Instructions section from thread metadata.

    Instructions are derived dynamically: state drives the primary action,
    playbook/auto_reply_mode/follow_up/goal drive the supporting lines.
    """
    lines = ["## Agent Instructions"]

    # Primary action based on state
    state = thread.state or "NEW"
    action_label = _STATE_ACTION_LABELS.get(state, f"Handle thread (state: {state})")
    lines.append(f"- **Action:** {action_label}")

    # Playbook instruction
    if thread.playbook:
        lines.append(f"- **Playbook:** Follow `{thread.playbook}` template")

    # Auto-reply instruction
    auto_reply_mode = thread.auto_reply_mode or "off"
    reply_label = _AUTO_REPLY_LABELS.get(
        auto_reply_mode, f"Auto-reply mode: {auto_reply_mode}"
    )
    lines.append(f"- **Auto-reply:** {reply_label}")

    # Follow-up instruction — only meaningful when not in a terminal state
    terminal_states = {"GOAL_MET", "ARCHIVED"}
    if state not in terminal_states:
        if thread.next_follow_up_date:
            follow_up_date_str = thread.next_follow_up_date.strftime("%Y-%m-%d")
            if state == "FOLLOW_UP":
                lines.append(
                    f"- **Follow-up:** Overdue — send follow-up now"
                    f" (was due {follow_up_date_str})"
                )
            else:
                lines.append(
                    f"- **Follow-up:** If no reply by {follow_up_date_str},"
                    " send a follow-up"
                )
        else:
            lines.append(
                f"- **Follow-up:** Schedule check every"
                f" {thread.follow_up_days or 3} days"
            )

    # Goal-check instruction — only when a goal is active
    if thread.goal and thread.goal_status == "in_progress":
        criteria_hint = (
            f" ({thread.acceptance_criteria})"
            if thread.acceptance_criteria
            else ""
        )
        lines.append(
            f"- **Goal check:** When reply received, evaluate whether"
            f" the goal is met{criteria_hint}"
        )
    elif thread.goal and thread.goal_status == "met":
        lines.append("- **Goal check:** Goal already met — no further evaluation needed")

    return "\n".join(lines)


async def generate_brief(thread_id: int) -> str | None:
    """Generate a structured markdown brief for a thread.

    Returns None when the thread or its emails cannot be found.
    """
    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return None

        # Get emails sorted chronologically
        result = await session.execute(
            select(Email)
            .where(Email.thread_id == thread_id)
            .order_by(Email.date.asc().nullslast())
        )
        emails = result.scalars().all()
        if not emails:
            return None

        # Collect unique participants
        participants: set[str] = set()
        for email in emails:
            if email.from_address:
                participants.add(email.from_address)
            for addr in (email.to_addresses or []):
                participants.add(addr)

        # Fetch contact info for the primary non-self participant
        own_email = "athenacapitao@gmail.com"
        other_participants = [p for p in participants if p != own_email]
        contact_info = ""
        if other_participants:
            contact = (
                await session.execute(
                    select(Contact).where(Contact.email == other_participants[0])
                )
            ).scalar_one_or_none()
            if contact:
                parts: list[str] = []
                if contact.name:
                    parts.append(contact.name)
                if contact.relationship_type and contact.relationship_type != "unknown":
                    parts.append(f"Relationship: {contact.relationship_type}")
                if contact.preferred_style:
                    parts.append(f"Prefers {contact.preferred_style} emails")
                if contact.communication_frequency:
                    parts.append(f"Communicates {contact.communication_frequency}")
                contact_info = ". ".join(parts)

        # Last email summary
        last = emails[-1]
        last_direction = "You" if last.is_sent else (last.from_address or "Unknown")
        last_date = last.date.strftime("%b %d") if last.date else "Unknown"
        last_snippet = (last.body_plain or "")[:200].replace("\n", " ").strip()

        # Overall sentiment from the three most recent emails
        recent_sentiments = [e.sentiment for e in emails[-3:] if e.sentiment]
        sentiment_str = ", ".join(recent_sentiments) if recent_sentiments else "unknown"

        # Follow-up schedule display
        follow_up_days = thread.follow_up_days or 3
        if thread.next_follow_up_date:
            next_date_str = thread.next_follow_up_date.strftime("%Y-%m-%d")
            follow_up_display = f"{follow_up_days} days (next: {next_date_str})"
        else:
            follow_up_display = f"{follow_up_days} days (not scheduled)"

        # ---------------------------------------------------------------
        # Build the brief line by line
        # ---------------------------------------------------------------
        lines = [
            f"## Thread Brief: {thread.subject or '(no subject)'}",
            f"- **Thread ID:** {thread.id}",
            f"- **Participants:** {', '.join(participants)}",
            f"- **State:** {thread.state}",
            f"- **Priority:** {thread.priority or 'unscored'} | "
            f"**Sentiment:** {sentiment_str} | "
            f"**Security:** {thread.security_score_avg or 'unscored'}/100",
        ]

        if thread.category:
            lines.append(f"- **Category:** {thread.category}")
        if thread.summary:
            lines.append(f"- **Summary:** {thread.summary}")

        # Goal block — only shown when a goal is set
        if thread.goal:
            lines.append(f"- **Goal:** {thread.goal}")
            if thread.acceptance_criteria:
                lines.append(
                    f"- **Acceptance Criteria:** {thread.acceptance_criteria}"
                )
            if thread.goal_status:
                lines.append(f"- **Goal Status:** {thread.goal_status}")

        # Playbook — only shown when set
        if thread.playbook:
            lines.append(f"- **Playbook:** {thread.playbook}")

        # Auto-reply mode — always shown; agent must know whether to draft or send
        lines.append(f"- **Auto-Reply:** {thread.auto_reply_mode or 'off'}")

        # Follow-up schedule — always shown; agent needs to know the cadence
        lines.append(f"- **Follow-up:** {follow_up_display}")

        lines.append(
            f"- **Last message:** {last_direction} ({last_date})"
            f" — \"{last_snippet}\""
        )
        lines.append(f"- **Email count:** {len(emails)}")

        if contact_info:
            lines.append(f"- **Contact:** {contact_info}")
        if thread.notes:
            lines.append(f"- **Notes:** {thread.notes}")

        # Agent instructions — dynamic section at the bottom
        lines.append("")
        lines.append(_build_agent_instructions(thread))

        brief = "\n".join(lines)
        logger.debug(f"Generated brief for thread {thread_id}")
        return brief
