"""Input/output guardrails for enterprise multi-agent runs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from utils.constants import (
    MAX_QUERY_LENGTH,
    MAX_WORK_PRODUCT_CHARS,
    PII_PATTERNS,
    PROMPT_INJECTION_MARKERS,
    SECRET_PATTERNS,
)


@dataclass
class GuardrailResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)

    def merge(self, other: "GuardrailResult") -> "GuardrailResult":
        return GuardrailResult(
            ok=self.ok and other.ok,
            reasons=self.reasons + other.reasons,
            findings=self.findings + other.findings,
        )


def _matches(patterns: tuple[str, ...], text: str) -> List[str]:
    hits: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text or ""):
            snippet = match.group(0)
            redacted = snippet[:4] + "…" if len(snippet) > 8 else "***"
            hits.append(f"{pattern[:24]}… -> {redacted}")
    return hits


def validate_user_query(query: str) -> GuardrailResult:
    reasons: List[str] = []
    findings: List[str] = []
    text = (query or "").strip()

    if not text:
        reasons.append("Empty query")
    if len(text) > MAX_QUERY_LENGTH:
        reasons.append(f"Query exceeds {MAX_QUERY_LENGTH} characters")

    lowered = text.lower()
    for marker in PROMPT_INJECTION_MARKERS:
        if marker in lowered:
            findings.append(f"Possible prompt-injection marker: '{marker}'")
            reasons.append("Query contains prompt-injection language")
            break

    secret_hits = _matches(SECRET_PATTERNS, text)
    if secret_hits:
        findings.extend(secret_hits)
        reasons.append("Query appears to contain secrets/credentials")

    return GuardrailResult(ok=not reasons, reasons=reasons, findings=findings)


def scan_text_for_secrets(text: str) -> GuardrailResult:
    hits = _matches(SECRET_PATTERNS, text or "")
    if not hits:
        return GuardrailResult(ok=True)
    return GuardrailResult(
        ok=False,
        reasons=["Potential secrets detected in work product"],
        findings=hits,
    )


def scan_text_for_pii(text: str) -> GuardrailResult:
    hits = _matches(PII_PATTERNS, text or "")
    if not hits:
        return GuardrailResult(ok=True)
    return GuardrailResult(
        ok=True,  # warn-only by default
        reasons=["Possible PII detected (warning)"],
        findings=hits,
    )


def enforce_work_product_size(text: str) -> GuardrailResult:
    if len(text or "") <= MAX_WORK_PRODUCT_CHARS:
        return GuardrailResult(ok=True)
    return GuardrailResult(
        ok=False,
        reasons=[f"Work product exceeds {MAX_WORK_PRODUCT_CHARS} characters"],
    )


def sanitize_for_prompt(text: str, limit: int = 6000) -> str:
    """Trim oversized context before LLM calls."""
    content = text or ""
    if len(content) <= limit:
        return content
    return content[:limit] + "\n\n…[truncated for enterprise context budget]"
