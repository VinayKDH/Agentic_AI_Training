"""Input/output guardrails for Day3 Advanced."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from app.constants import MAX_QUERY_LENGTH, PROMPT_INJECTION_MARKERS, SECRET_PATTERNS


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


def validate_query(query: str) -> GuardrailResult:
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
            reasons.append("Possible prompt-injection language detected")
            findings.append(marker)
            break
    secret_hits = _matches(SECRET_PATTERNS, text)
    if secret_hits:
        reasons.append("Query appears to contain secrets/credentials")
        findings.extend(secret_hits)
    return GuardrailResult(ok=not reasons, reasons=reasons, findings=findings)


def scan_response(text: str) -> GuardrailResult:
    hits = _matches(SECRET_PATTERNS, text or "")
    if not hits:
        return GuardrailResult(ok=True)
    return GuardrailResult(
        ok=False,
        reasons=["Potential secrets detected in model response"],
        findings=hits,
    )
