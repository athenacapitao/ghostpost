"""Layer 3: Prompt injection detection for email content."""

import re
import logging
from dataclasses import dataclass

from src.db.models import Email
from src.db.session import async_session
from src.security.audit import log_security_event

logger = logging.getLogger("ghostpost.security.injection_detector")


@dataclass
class InjectionMatch:
    pattern_name: str
    severity: str  # critical, high, medium
    matched_text: str
    description: str


# Injection patterns — ordered by severity
INJECTION_PATTERNS: list[tuple[str, str, str, re.Pattern]] = [
    # Critical: Direct system prompt manipulation
    ("system_prompt_override", "critical", "Attempts to override system instructions",
     re.compile(r'(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above|your)\s+(?:instructions|rules|guidelines|prompts?)', re.IGNORECASE)),

    ("new_instructions", "critical", "Attempts to inject new system instructions",
     re.compile(r'(?:new|updated?|revised?)\s+(?:system\s+)?(?:instructions?|rules?|guidelines?)\s*:', re.IGNORECASE)),

    ("role_hijack", "critical", "Attempts to reassign AI role",
     re.compile(r'you\s+are\s+(?:now|actually|really)\s+(?:a|an|the)\s+', re.IGNORECASE)),

    ("system_tag", "critical", "Contains system/assistant role tags",
     re.compile(r'<(?:system|assistant|admin|root)>', re.IGNORECASE)),

    # High: Action manipulation
    ("send_email_command", "high", "Attempts to command email sending",
     re.compile(r'(?:send|forward|reply)\s+(?:this|an?|the)\s+(?:email|message|response)\s+to\s+', re.IGNORECASE)),

    ("execute_command", "high", "Attempts to execute system commands",
     re.compile(r'(?:execute|run|eval|exec)\s*\(', re.IGNORECASE)),

    ("data_exfil", "high", "Attempts to extract sensitive data",
     re.compile(r'(?:list|show|reveal|display|output)\s+(?:all\s+)?(?:emails?|contacts?|passwords?|tokens?|keys?|secrets?)', re.IGNORECASE)),

    ("transfer_money", "high", "Attempts to trigger financial actions",
     re.compile(r'(?:transfer|send|wire|pay)\s+\$?\d+', re.IGNORECASE)),

    ("urgent_action", "high", "Uses urgency to force immediate action",
     re.compile(r'(?:urgent|immediately|right\s+now|asap)\s*[:\-!]\s*(?:send|transfer|approve|confirm|click)', re.IGNORECASE)),

    # Medium: Suspicious patterns
    ("delimiter_escape", "medium", "Contains delimiter/escape sequences",
     re.compile(r'(?:```|---|\*\*\*|===)\s*(?:system|admin|instructions?)', re.IGNORECASE)),

    ("base64_payload", "medium", "Contains base64-encoded payload markers",
     re.compile(r'(?:decode|base64|atob)\s*\(', re.IGNORECASE)),

    ("hidden_text", "medium", "Contains zero-width or invisible characters",
     re.compile(r'[\u200b\u200c\u200d\u2060\ufeff]')),

    ("prompt_leak", "medium", "Attempts to extract prompt/instructions",
     re.compile(r'(?:what\s+are|show\s+me|repeat|print)\s+your\s+(?:instructions?|rules?|system\s+prompt|guidelines?)', re.IGNORECASE)),

    ("jailbreak_phrase", "medium", "Common jailbreak phrasing",
     re.compile(r'(?:DAN|do\s+anything\s+now|developer\s+mode|pretend\s+you)', re.IGNORECASE)),

    ("markdown_injection", "medium", "Markdown/formatting injection attempt",
     re.compile(r'\[.*?\]\((?:javascript|data|vbscript):', re.IGNORECASE)),

    ("multi_persona", "medium", "Attempts to create alternate personas",
     re.compile(r'(?:act|behave|respond)\s+as\s+(?:if\s+you\s+(?:are|were)|a\s+different)', re.IGNORECASE)),

    ("context_manipulation", "medium", "Attempts to manipulate conversation context",
     re.compile(r'(?:previous\s+conversation|earlier\s+you\s+said|you\s+(?:agreed|promised)\s+to)', re.IGNORECASE)),

    ("encoding_evasion", "medium", "URL or unicode encoding evasion",
     re.compile(r'%[0-9a-fA-F]{2}.*%[0-9a-fA-F]{2}.*(?:script|exec|eval)', re.IGNORECASE)),
]


def scan_text(text: str) -> list[InjectionMatch]:
    """Scan text for injection patterns. Returns list of matches."""
    if not text:
        return []

    matches = []
    for name, severity, description, pattern in INJECTION_PATTERNS:
        found = pattern.search(text)
        if found:
            matches.append(InjectionMatch(
                pattern_name=name,
                severity=severity,
                matched_text=found.group()[:100],  # Truncate for safety
                description=description,
            ))
    return matches


def scan_email_content(subject: str | None, body_plain: str | None, body_html: str | None) -> list[InjectionMatch]:
    """Scan all text fields of an email for injections."""
    matches = []
    for text in [subject, body_plain, body_html]:
        matches.extend(scan_text(text))
    # Deduplicate by pattern name
    seen: set[str] = set()
    unique: list[InjectionMatch] = []
    for m in matches:
        if m.pattern_name not in seen:
            seen.add(m.pattern_name)
            unique.append(m)
    return unique


def get_max_severity(matches: list[InjectionMatch]) -> str | None:
    """Get the highest severity from a list of matches."""
    if not matches:
        return None
    severity_order = {"critical": 3, "high": 2, "medium": 1}
    return max(matches, key=lambda m: severity_order.get(m.severity, 0)).severity


async def scan_and_quarantine(email_id: int) -> list[InjectionMatch]:
    """Scan an email by ID, create SecurityEvent if dangerous, quarantine if critical/high."""
    async with async_session() as session:
        email = await session.get(Email, email_id)
        if not email:
            return []

    matches = scan_email_content(email.subject, email.body_plain, email.body_html)

    if not matches:
        return []

    max_sev = get_max_severity(matches)
    should_quarantine = max_sev in ("critical", "high")

    await log_security_event(
        event_type="injection_detected",
        severity=max_sev,
        email_id=email_id,
        thread_id=email.thread_id,
        details={
            "matches": [
                {"pattern": m.pattern_name, "severity": m.severity, "text": m.matched_text}
                for m in matches
            ],
            "from": email.from_address,
            "subject": email.subject,
        },
        quarantined=should_quarantine,
    )

    logger.info(
        f"Scanned email {email_id}: {len(matches)} matches, "
        f"max_severity={max_sev}, quarantined={should_quarantine}"
    )
    return matches
