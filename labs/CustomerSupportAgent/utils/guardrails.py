"""Guardrails for inbound email and outbound replies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from utils.constants import MAX_EMAIL_LENGTH, SECRET_PATTERNS


@dataclass
class GuardrailResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)


def _matches(patterns: tuple[str, ...], text: str) -> List[str]:
    hits: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text or ""):
            snippet = match.group(0)
            hits.append(snippet[:4] + "…" if len(snippet) > 8 else "***")
    return hits


def validate_inbound_email(content: str, sender_email: str) -> GuardrailResult:
    reasons: List[str] = []
    findings: List[str] = []
    text = (content or "").strip()
    if not text:
        reasons.append("Empty email content")
    if len(text) > MAX_EMAIL_LENGTH:
        reasons.append(f"Email exceeds {MAX_EMAIL_LENGTH} characters")
    if not sender_email or "@" not in sender_email:
        reasons.append("Invalid sender email")
    findings.extend(_matches(SECRET_PATTERNS, text))
    if findings:
        reasons.append("Inbound email may contain secrets — redact in replies")
    hard_block = [
        reason
        for reason in reasons
        if reason.startswith("Empty")
        or reason.startswith("Email exceeds")
        or reason.startswith("Invalid")
    ]
    return GuardrailResult(ok=not hard_block, reasons=reasons, findings=findings)


def scan_outbound_reply(text: str) -> GuardrailResult:
    hits = _matches(SECRET_PATTERNS, text or "")
    if hits:
        return GuardrailResult(
            ok=False,
            reasons=["Outbound reply contains potential secrets/card data"],
            findings=hits,
        )
    return GuardrailResult(ok=True)


def redact_secrets(text: str) -> str:
    redacted = text or ""
    for pattern in SECRET_PATTERNS:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted
