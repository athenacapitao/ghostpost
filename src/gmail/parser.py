"""Parse Gmail API responses into structured data."""

import base64
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger("ghostpost.gmail.parser")


def parse_headers(msg: dict) -> dict[str, str]:
    """Extract headers from a Gmail message payload into a dict."""
    headers = {}
    for h in msg.get("payload", {}).get("headers", []):
        headers[h["name"].lower()] = h["value"]
    return headers


def parse_address(raw: str) -> tuple[str | None, str]:
    """Extract (name, email) from 'Name <email>' format."""
    match = re.match(r"^(.+?)\s*<(.+?)>$", raw.strip())
    if match:
        return match.group(1).strip().strip('"'), match.group(2).strip()
    return None, raw.strip()


def parse_address_list(raw: str | None) -> list[str]:
    """Split comma-separated address list."""
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def parse_date(headers: dict[str, str]) -> datetime | None:
    """Parse the Date header into a timezone-aware datetime."""
    date_str = headers.get("date")
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def walk_parts(payload: dict) -> tuple[str | None, str | None, list[dict]]:
    """Recursively walk MIME parts to extract plain text, HTML, and attachment metadata."""
    body_plain = None
    body_html = None
    attachments = []

    def _walk(part: dict):
        nonlocal body_plain, body_html
        mime_type = part.get("mimeType", "")
        filename = part.get("filename", "")
        body_data = part.get("body", {})

        # Attachment: has filename or is not text
        if filename and body_data.get("attachmentId"):
            attachments.append({
                "filename": filename,
                "content_type": mime_type,
                "size": body_data.get("size", 0),
                "gmail_attachment_id": body_data["attachmentId"],
            })
            return

        if mime_type == "text/plain" and not body_plain:
            data = body_data.get("data", "")
            if data:
                body_plain = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime_type == "text/html" and not body_html:
            data = body_data.get("data", "")
            if data:
                body_html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        # Recurse into multipart
        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)
    return body_plain, body_html, attachments


def parse_message(msg: dict) -> dict:
    """Parse a full Gmail message dict into our model-ready format."""
    headers = parse_headers(msg)
    payload = msg.get("payload", {})
    body_plain, body_html, attachment_metas = walk_parts(payload)

    from_name, from_email = parse_address(headers.get("from", ""))
    to_list = parse_address_list(headers.get("to"))
    cc_list = parse_address_list(headers.get("cc"))
    bcc_list = parse_address_list(headers.get("bcc"))

    date = parse_date(headers)
    internal_date_ms = msg.get("internalDate")
    received_at = None
    if internal_date_ms:
        received_at = datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)

    label_ids = msg.get("labelIds", [])

    return {
        "gmail_id": msg["id"],
        "gmail_thread_id": msg["threadId"],
        "message_id": headers.get("message-id"),
        "from_address": from_email,
        "from_name": from_name,
        "to_addresses": to_list,
        "cc": cc_list,
        "bcc": bcc_list,
        "subject": headers.get("subject"),
        "body_plain": body_plain,
        "body_html": body_html,
        "date": date,
        "received_at": received_at,
        "headers": headers,
        "attachments": attachment_metas,
        "is_read": "UNREAD" not in label_ids,
        "is_sent": "SENT" in label_ids,
        "is_draft": "DRAFT" in label_ids,
    }
