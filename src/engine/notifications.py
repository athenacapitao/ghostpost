"""Notification filtering engine — checks settings and writes alerts for OpenClaw."""

import logging
import os
from datetime import datetime, timezone

from src.api.events import publish_event
from src.db.models import Setting
from src.db.session import async_session
from src.engine.context_writer import _append_changelog, _atomic_write

logger = logging.getLogger("ghostpost.engine.notifications")

ALERTS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "context", "ALERTS.md")
)

# Map event types to their setting keys
EVENT_SETTING_MAP = {
    "new_high_urgency_email": "notification_new_email",
    "goal_met": "notification_goal_met",
    "security_alert": "notification_security_alert",
    "injection_detected": "notification_security_alert",
    "anomaly_detected": "notification_security_alert",
    "email_quarantined": "notification_security_alert",
    "draft_ready": "notification_draft_ready",
    "stale_thread": "notification_stale_thread",
    "commitment_detected": "notification_security_alert",
    "thread_composed": "notification_new_email",
}

# Default values for notification settings (must match settings.py DEFAULTS)
NOTIFICATION_DEFAULTS = {
    "notification_new_email": "true",
    "notification_goal_met": "true",
    "notification_security_alert": "true",
    "notification_draft_ready": "true",
    "notification_stale_thread": "true",
}

# Severity badge mapping for ALERTS.md formatting
SEVERITY_BADGES = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "info": "INFO",
}


async def _get_notification_setting(key: str) -> bool:
    """Check if a notification setting is enabled, falling back to defaults."""
    async with async_session() as session:
        setting = await session.get(Setting, key)
        if setting:
            return setting.value.lower() in ("true", "1", "yes")
    return NOTIFICATION_DEFAULTS.get(key, "true").lower() == "true"


async def should_notify(event_type: str) -> bool:
    """Return True if the notification setting for this event type is enabled."""
    setting_key = EVENT_SETTING_MAP.get(event_type)
    if not setting_key:
        logger.warning(f"Unknown event type for notification check: {event_type}")
        return False
    return await _get_notification_setting(setting_key)


async def dispatch_notification(
    event_type: str,
    title: str,
    message: str,
    thread_id: int | None = None,
    severity: str = "info",
    metadata: dict | None = None,
) -> bool:
    """Dispatch a notification if the matching setting is enabled.

    Writes to ALERTS.md for OpenClaw consumption and publishes a Redis event
    for WebSocket push. Returns True if the notification was dispatched,
    False if it was filtered out by the user's setting.
    """
    if not await should_notify(event_type):
        logger.debug(f"Notification filtered out: {event_type} (setting disabled)")
        return False

    alert: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "severity": severity,
        "title": title,
        "message": message,
        "thread_id": thread_id,
    }
    if metadata:
        alert["metadata"] = metadata

    _append_alert(alert)

    # Best-effort Redis publish for WebSocket delivery — failure must not block callers
    try:
        await publish_event("notification", alert)
    except Exception as exc:
        logger.error(f"Failed to publish notification event via Redis: {exc}")

    logger.info(f"Notification dispatched: [{severity}] {title}")
    return True


def _parse_alert_entries(content: str) -> list[str]:
    """Split ALERTS.md content into individual entry strings."""
    raw_parts = content.split("\n- ")
    entries: list[str] = []
    for part in raw_parts[1:]:  # skip header section before first "- " entry
        entries.append("- " + part)
    return entries


def _make_dedup_key(thread_id: int | None, message: str) -> str:
    """Build a deduplication key from the thread ID and message text."""
    return f"{thread_id}|{message.strip()}"


def _entry_dedup_key(entry: str) -> str:
    """Extract a deduplication key from a raw entry string.

    The key is derived from the thread-id token (if present) and the second
    line of the entry, which holds the message body.
    """
    lines = entry.strip().splitlines()
    header_line = lines[0] if lines else ""
    message_line = lines[1].strip() if len(lines) > 1 else ""

    # Extract thread id from "... (thread #42)" suffix
    thread_id_str: str | None = None
    if "(thread #" in header_line:
        try:
            thread_id_str = header_line.split("(thread #")[1].rstrip(")")
        except IndexError:
            pass

    return f"{thread_id_str}|{message_line}"


def _append_alert(alert: dict) -> None:
    """Append one alert entry to ALERTS.md, keeping the last 50 entries.

    Deduplication: if an identical alert (same thread ID + same message text)
    already exists within the most recent 20 entries, the write is skipped.
    """
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)

    # Format timestamp as "YYYY-MM-DD HH:MM" (without timezone noise for readability)
    timestamp = alert["timestamp"][:19].replace("T", " ")
    severity_label = SEVERITY_BADGES.get(alert["severity"], alert["severity"].upper())

    new_entry = f"- **[{timestamp}]** [{severity_label}] {alert['title']}"
    if alert.get("thread_id"):
        new_entry += f" (thread #{alert['thread_id']})"
    new_entry += f"\n  {alert['message']}\n"

    # Read and preserve the last 49 existing entries (we are about to add one)
    existing_entries: list[str] = []
    is_new_file = not os.path.isfile(ALERTS_FILE) or os.path.getsize(ALERTS_FILE) == 0
    if not is_new_file:
        with open(ALERTS_FILE) as f:
            content = f.read()
        existing_entries = _parse_alert_entries(content)

    # Deduplication check: skip if the same alert appears in the 20 most recent
    # entries.  The list is newest-first, so the first 20 elements are the most
    # recent 20 in chronological terms.
    incoming_key = _make_dedup_key(alert.get("thread_id"), alert["message"])
    recent_window = existing_entries[:20]
    for recent_entry in recent_window:
        if _entry_dedup_key(recent_entry) == incoming_key:
            logger.debug(
                f"Duplicate alert suppressed (thread_id={alert.get('thread_id')}, "
                f"message='{alert['message'][:60]}')"
            )
            return

    existing_entries = existing_entries[-49:]

    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # Build the full file content in memory then write atomically so readers
    # never observe a partial file mid-write.
    # On first creation, include a relationship note so the agent knows where
    # security-specific alerts live.
    header_note = (
        "_Operational alerts. For security-specific alerts see SECURITY_ALERTS.md._\n\n"
        if is_new_file
        else ""
    )
    parts = [
        "# Active Alerts\n",
        "<!-- schema_version: 1 -->\n",
        header_note,
        f"_Last updated: {updated_at}_\n\n",
        new_entry,
    ]
    for entry in existing_entries:
        normalized = entry if entry.startswith("- ") else "- " + entry
        parts.append(normalized if normalized.endswith("\n") else normalized + "\n")
    _atomic_write(ALERTS_FILE, "".join(parts))


def cleanup_alerts() -> int:
    """Remove duplicate entries from ALERTS.md and trim to the last 50.

    Reads the file, keeps the first occurrence of each unique (thread_id,
    message) pair, trims the result to 50 entries, and rewrites the file.
    Returns the number of entries removed.
    """
    if not os.path.isfile(ALERTS_FILE):
        return 0

    with open(ALERTS_FILE) as f:
        content = f.read()

    entries = _parse_alert_entries(content)
    original_count = len(entries)

    # Deduplicate preserving order — keep the first occurrence of each key.
    seen_keys: set[str] = set()
    deduplicated: list[str] = []
    for entry in entries:
        key = _entry_dedup_key(entry)
        if key not in seen_keys:
            seen_keys.add(key)
            deduplicated.append(entry)

    # Keep only the most recent 50 after deduplication.
    trimmed = deduplicated[-50:]
    removed_count = original_count - len(trimmed)

    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        "# Active Alerts\n",
        "<!-- schema_version: 1 -->\n",
        f"_Last updated: {updated_at}_\n\n",
    ]
    for entry in trimmed:
        normalized = entry if entry.startswith("- ") else "- " + entry
        parts.append(normalized if normalized.endswith("\n") else normalized + "\n")
    _atomic_write(ALERTS_FILE, "".join(parts))

    logger.info(f"cleanup_alerts: removed {removed_count} duplicate/excess entries, {len(trimmed)} remain")
    return removed_count


# --- Convenience dispatchers for common event types ---

async def notify_new_email(thread_id: int, subject: str, sender: str, urgency: str) -> bool:
    """Notify about a new high-urgency or critical email.

    Returns False immediately for non-high/critical urgency so callers do not
    need to guard the call themselves.
    """
    if urgency not in ("high", "critical"):
        return False
    severity = "high" if urgency == "high" else "critical"
    _append_changelog(
        "new_email",
        f'Thread #{thread_id} "{subject}" from {sender}',
        severity.upper(),
    )
    return await dispatch_notification(
        event_type="new_high_urgency_email",
        title=f"High-urgency email from {sender}",
        message=f"Subject: {subject}. Urgency: {urgency}. Requires attention.",
        thread_id=thread_id,
        severity=severity,
    )


async def notify_goal_met(thread_id: int, subject: str, goal: str) -> bool:
    """Notify when a thread's goal has been achieved."""
    _append_changelog("goal_met", f"Thread #{thread_id} goal achieved", "INFO")
    return await dispatch_notification(
        event_type="goal_met",
        title=f"Goal achieved: {subject}",
        message=f"Goal '{goal}' has been met.",
        thread_id=thread_id,
        severity="info",
    )


async def notify_security_alert(
    thread_id: int | None,
    event_type: str,
    details: str,
    severity: str = "high",
) -> bool:
    """Notify about a security event (injection, anomaly, quarantine, commitment)."""
    thread_label = f"thread #{thread_id}" if thread_id is not None else "no thread"
    _append_changelog(
        "security_alert",
        f"{event_type} on {thread_label}",
        severity.upper(),
    )
    return await dispatch_notification(
        event_type=event_type,
        title=f"Security: {event_type.replace('_', ' ')}",
        message=details,
        thread_id=thread_id,
        severity=severity,
    )


async def notify_draft_ready(thread_id: int, subject: str, draft_id: int) -> bool:
    """Notify when an auto-generated draft is waiting for approval."""
    _append_changelog(
        "draft_ready",
        f"Draft #{draft_id} for thread #{thread_id} pending approval",
        "INFO",
    )
    return await dispatch_notification(
        event_type="draft_ready",
        title=f"Draft ready: {subject}",
        message=f"Draft #{draft_id} is waiting for approval.",
        thread_id=thread_id,
        severity="info",
    )


async def notify_thread_composed(thread_id: int, subject: str, to: str, goal: str | None = None) -> bool:
    """Notify that a new email was composed with a tracked thread."""
    message = f"New email to {to}. Subject: {subject}."
    if goal:
        message += f" Goal: {goal}."
    return await dispatch_notification(
        event_type="thread_composed",
        title=f"Thread created: {subject}",
        message=message,
        thread_id=thread_id,
        severity="info",
    )


async def notify_stale_thread(thread_id: int, subject: str, days: int) -> bool:
    """Notify that a thread has received no reply for the configured number of days."""
    _append_changelog(
        "stale_thread",
        f"Thread #{thread_id} no reply for {days}d",
        "MEDIUM",
    )
    return await dispatch_notification(
        event_type="stale_thread",
        title=f"Stale thread: {subject}",
        message=f"No reply received for {days} days. Follow-up recommended.",
        thread_id=thread_id,
        severity="medium",
    )
