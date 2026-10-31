"""Phase 10 unit tests: PII is redacted; real numbers are not."""

from __future__ import annotations

import pytest

from securerag.ingestion.pii import redact

# (text, expected_label) -- PII that MUST be redacted.
REDACT_CASES = [
    ("Email rohan.kapoor@acme.example today", "<EMAIL>"),
    ("Contact sneha.nair@acme.example", "<EMAIL>"),
    ("Call +91 98765 43210 now", "<PHONE>"),
    ("Mobile +91 9876543210", "<PHONE>"),
    ("Reach +91-91234-56780", "<PHONE>"),
    ("PAN ABCDE1234F on file", "<PAN>"),
    ("PAN PQRSX6789K", "<PAN>"),
    ("Aadhaar 1234 5678 9012", "<AADHAAR>"),
    ("Aadhaar 123456789012", "<AADHAAR>"),
    ("Aadhaar 4567-8901-2345", "<AADHAAR>"),
]

# Text that must be LEFT ALONE (real business numbers, dates, codes).
KEEP_CASES = [
    "The Q2 budget is INR 36 crore",
    "Health insurance floater INR 5,00,000",
    "Policy effective 2026-04-01",
    "Incident on 14 January 2026",
    "Error code ERR-4021 was resolved",
]


@pytest.mark.parametrize("text,label", REDACT_CASES)
def test_pii_is_redacted(text, label):
    redacted, found = redact(text)
    assert found is True
    assert label in redacted
    # the raw PII token should be gone
    assert "@acme.example" not in redacted
    assert "ABCDE1234F" not in redacted


@pytest.mark.parametrize("text", KEEP_CASES)
def test_real_numbers_are_not_redacted(text):
    redacted, found = redact(text)
    assert found is False
    assert redacted == text


def test_names_are_kept():
    # Policy: keep names (protected by ACL), redact contact/IDs only.
    text = "Employee: Rohan Kapoor, PAN ABCDE1234F"
    redacted, _ = redact(text)
    assert "Rohan Kapoor" in redacted
    assert "<PAN>" in redacted
