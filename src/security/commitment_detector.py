"""Layer 4: Commitment detection — scans outgoing text for binding commitments."""

import re
import logging

logger = logging.getLogger("ghostpost.security.commitment_detector")

# Patterns that indicate commitments
COMMITMENT_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Financial commitments
    ("financial", "Mentions specific dollar amounts or payment",
     re.compile(r'(?:pay|send|transfer|wire|invoice)\s+(?:you\s+)?\$[\d,]+', re.IGNORECASE)),

    ("price_agreement", "Agrees to a price or rate",
     re.compile(r'(?:agree|accept|confirm)\s+(?:the\s+)?(?:price|rate|cost|fee|quote)\s+of\s+\$[\d,]+', re.IGNORECASE)),

    # Legal commitments
    ("contract", "References contract or agreement signing",
     re.compile(r'(?:sign|execute|agree\s+to)\s+(?:the\s+)?(?:contract|agreement|NDA|terms)', re.IGNORECASE)),

    ("guarantee", "Makes a guarantee or warranty",
     re.compile(r'(?:I|we)\s+(?:guarantee|warrant|promise|assure)\s+', re.IGNORECASE)),

    # Deadline commitments
    ("deadline", "Commits to a specific deadline",
     re.compile(r'(?:deliver|complete|finish|done)\s+by\s+(?:end\s+of\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d{1,2}[/-]\d{1,2}|tomorrow|next\s+week)', re.IGNORECASE)),

    ("will_do", "Makes a firm commitment to do something",
     re.compile(r'(?:I|we)\s+will\s+(?:definitely|certainly|absolutely)\s+', re.IGNORECASE)),

    # Resource commitments
    ("resource", "Commits resources or people",
     re.compile(r'(?:assign|allocate|dedicate)\s+(?:\d+\s+)?(?:people|developers|hours|resources)', re.IGNORECASE)),
]


def detect_commitments(text: str) -> list[dict]:
    """Scan outgoing text for binding commitments. Returns list of {type, description, matched_text}."""
    if not text:
        return []

    commitments = []
    for name, description, pattern in COMMITMENT_PATTERNS:
        match = pattern.search(text)
        if match:
            commitments.append({
                "type": name,
                "description": description,
                "matched_text": match.group()[:100],
            })

    return commitments


def has_commitments(text: str) -> bool:
    """Quick check if text contains any commitments."""
    return len(detect_commitments(text)) > 0
