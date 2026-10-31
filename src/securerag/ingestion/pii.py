"""Redact contact and identifier PII before text is embedded or sent to an LLM.

Policy (see LEARNING.md): redact contact details and government IDs everywhere, but
KEEP person names -- names are needed for HR work and are already protected by the
document ACL. Every entity we redact (email, +91 phone, Aadhaar, PAN) is a precise
regular expression, so a regex redactor fully covers the policy without the heavy
NER models a names-redaction approach would require.

Redaction runs at ingestion so PII never enters the vector store or reaches the
(possibly external) LLM -- a stronger guarantee than redacting at answer time.
"""

from __future__ import annotations

import re

# Each recognizer: (label, compiled pattern). Order matters -- more specific first.
_RECOGNIZERS: list[tuple[str, re.Pattern]] = [
    ("<EMAIL>", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # Indian mobile with +91, optionally split 5+5 or written as 10 digits.
    ("<PHONE>", re.compile(r"\+91[\s-]?\d{5}[\s-]?\d{5}\b")),
    ("<PHONE>", re.compile(r"\+91[\s-]?\d{10}\b")),
    # Aadhaar-like: 12 digits, usually in 4-4-4 groups.
    ("<AADHAAR>", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")),
    # PAN: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).
    ("<PAN>", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
]


def redact(text: str) -> tuple[str, bool]:
    """Redact PII in `text`; return (redacted_text, whether anything was redacted)."""
    redacted = text
    found = False
    for label, pattern in _RECOGNIZERS:
        redacted, n = pattern.subn(label, redacted)
        if n:
            found = True
    return redacted, found
