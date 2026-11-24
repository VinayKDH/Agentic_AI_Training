"""Enterprise quality / compliance policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from utils.constants import (
    BLOCK_ON_SECRET_FINDINGS,
    ENTERPRISE_POLICY_CHECKLIST,
    MIN_APPROVAL_SCORE,
    MIN_REVIEW_SCORE,
    REQUIRE_SOURCES_FOR_RESEARCH,
    REQUIRE_USAGE_NOTES_FOR_CODE,
)
from utils.guardrails import (
    enforce_work_product_size,
    scan_text_for_pii,
    scan_text_for_secrets,
)


@dataclass
class PolicyEvaluation:
    passed: bool
    score_floor: int
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checklist: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score_floor": self.score_floor,
            "violations": self.violations,
            "warnings": self.warnings,
            "checklist": self.checklist,
        }


def evaluate_research_artifact(artifact: Dict[str, Any]) -> PolicyEvaluation:
    findings = artifact.get("findings") or ""
    sources = artifact.get("sources") or []
    violations: List[str] = []
    warnings: List[str] = []

    size = enforce_work_product_size(findings)
    if not size.ok:
        violations.extend(size.reasons)

    secrets = scan_text_for_secrets(findings)
    if not secrets.ok and BLOCK_ON_SECRET_FINDINGS:
        violations.extend(secrets.reasons)

    pii = scan_text_for_pii(findings)
    warnings.extend(pii.reasons)

    if REQUIRE_SOURCES_FOR_RESEARCH and not sources:
        # Soft requirement: warn unless findings claim citations inline
        if "http://" not in findings and "https://" not in findings:
            warnings.append("Research findings lack explicit sources/URLs")

    if len(findings.strip()) < 40:
        violations.append("Research findings are too thin for enterprise handoff")

    return PolicyEvaluation(
        passed=not violations,
        score_floor=MIN_REVIEW_SCORE,
        violations=violations,
        warnings=warnings,
        checklist=list(ENTERPRISE_POLICY_CHECKLIST),
    )


def evaluate_code_artifact(artifact: Dict[str, Any]) -> PolicyEvaluation:
    code = artifact.get("code") or ""
    usage = artifact.get("usage") or ""
    explanation = artifact.get("explanation") or ""
    blob = f"{code}\n{usage}\n{explanation}"
    violations: List[str] = []
    warnings: List[str] = []

    size = enforce_work_product_size(blob)
    if not size.ok:
        violations.extend(size.reasons)

    secrets = scan_text_for_secrets(blob)
    if not secrets.ok and BLOCK_ON_SECRET_FINDINGS:
        violations.extend(secrets.reasons)
        violations.extend(secrets.findings[:3])

    if REQUIRE_USAGE_NOTES_FOR_CODE and len(usage.strip()) < 8:
        violations.append("Code artifact missing usage/run notes")

    if not code.strip():
        violations.append("Code artifact is empty")

    unsafe_markers = ("eval(", "exec(", "pickle.loads(", "subprocess.call(")
    if any(marker in code for marker in unsafe_markers):
        warnings.append("Potentially unsafe API usage detected — reviewer must justify")

    return PolicyEvaluation(
        passed=not violations,
        score_floor=MIN_APPROVAL_SCORE,
        violations=violations,
        warnings=warnings,
        checklist=list(ENTERPRISE_POLICY_CHECKLIST),
    )


def evaluate_work_product(task_assigned_to: str, work_product: Dict[str, Any]) -> PolicyEvaluation:
    if "code" in work_product or task_assigned_to == "coder":
        return evaluate_code_artifact(work_product)
    return evaluate_research_artifact(work_product)


def apply_policy_to_review(
    review: Dict[str, Any],
    policy: PolicyEvaluation,
) -> Dict[str, Any]:
    """Force revise when deterministic policy checks fail."""
    updated = dict(review)
    notes: List[str] = []
    if policy.violations:
        updated["approved"] = False
        updated["decision"] = "needs_revision"
        if int(updated.get("score") or 10) > (MIN_REVIEW_SCORE - 1):
            updated["score"] = max(1, MIN_REVIEW_SCORE - 1)
        notes.append("Policy gate failed:")
        notes.extend(f"- {item}" for item in policy.violations)
    if policy.warnings:
        notes.append("Policy warnings:")
        notes.extend(f"- {item}" for item in policy.warnings)
    if notes:
        feedback = updated.get("feedback") or ""
        updated["feedback"] = f"{feedback}\n\n" + "\n".join(notes)
        updated["policy"] = policy.to_dict()
    return updated
