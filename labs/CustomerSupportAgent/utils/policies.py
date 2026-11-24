"""Enterprise support policy helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from utils.constants import SLA_TARGETS_HOURS, SUPPORT_POLICY_CHECKLIST
from utils.guardrails import scan_outbound_reply


def sla_hours_for_urgency(urgency: str) -> int:
    return SLA_TARGETS_HOURS.get((urgency or "medium").lower(), 24)


def requires_human_review(classification: Dict[str, Any] | None, draft: str | None) -> bool:
    if not classification:
        return True
    urgency = classification.get("urgency", "medium")
    intent = classification.get("intent", "")
    if urgency == "critical":
        return True
    if intent in {"complex", "billing"}:
        return True
    if not draft:
        return True
    return False


def evaluate_draft(draft: str, classification: Dict[str, Any] | None) -> Dict[str, Any]:
    violations: List[str] = []
    warnings: List[str] = []
    scan = scan_outbound_reply(draft or "")
    if not scan.ok:
        violations.extend(scan.reasons)
    if classification and classification.get("intent") == "bug" and "BUG-" not in (draft or ""):
        warnings.append("Bug reply should reference a ticket ID when available")
    if len((draft or "").strip()) < 40:
        violations.append("Draft response too short for enterprise handoff")
    return {
        "passed": not violations,
        "violations": violations,
        "warnings": warnings,
        "checklist": list(SUPPORT_POLICY_CHECKLIST),
    }
