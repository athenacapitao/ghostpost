"""Layer 1+2: Input sanitization and content isolation for email data."""

import html
import re
import logging

logger = logging.getLogger("ghostpost.security.sanitizer")

# Layer 1: Strip dangerous HTML constructs
def sanitize_html(text: str | None) -> str:
    """Strip HTML comments, script tags, and decode entities."""
    if not text:
        return ""
    # Remove HTML comments — loop to handle nested/malformed comments
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # Strip any remaining orphaned --> or <!-- fragments
    text = re.sub(r'<!--?|-->', '', text)
    # Remove script tags entirely
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove style tags (CSS injection vectors)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove event handlers (onclick, onload, etc.)
    text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def sanitize_plain(text: str | None) -> str:
    """Normalize plain text — collapse whitespace, strip control chars."""
    if not text:
        return ""
    # Remove null bytes and control characters (except newline/tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Remove Unicode bidirectional and zero-width format characters
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]', '', text)
    return text.strip()


# Layer 2: Content isolation markers
ISOLATION_START = "=== UNTRUSTED EMAIL CONTENT START ==="
ISOLATION_END = "=== UNTRUSTED EMAIL CONTENT END ==="


def isolate_content(text: str) -> str:
    """Wrap email content in isolation markers for LLM consumption."""
    return f"{ISOLATION_START}\n{text}\n{ISOLATION_END}"


def is_isolated(text: str) -> bool:
    """Check if content is properly isolated."""
    return ISOLATION_START in text and ISOLATION_END in text
