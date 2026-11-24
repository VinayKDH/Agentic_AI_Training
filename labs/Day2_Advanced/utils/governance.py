"""Standard governance of agent autonomy (L0–L4).

Decision model:
- L0 Supervised: human gates on plan, each review, and final release
- L1 Assisted: human gates on plan + final release; escalate on reject
- L2 Conditional: autonomous within risk ceiling; escalate on reject/policy/high risk
- L3 High: escalate only for critical risk, hard policy fail, or severe score miss
- L4 Full: no human gates; hard guardrails + audit remain mandatory
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.constants import (
    AUTONOMY_DECISION_RIGHTS,
    AUTONOMY_LEVELS,
    DEFAULT_AUTONOMY_LEVEL,
    GOVERNANCE_FRAMEWORK_NAME,
    GOVERNANCE_FRAMEWORK_VERSION,
    MIN_REVIEW_SCORE,
)

_RISK_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_LEVEL_BY_ID = {item["id"]: item for item in AUTONOMY_LEVELS}


@dataclass
class GovernanceDecision:
    action: str
    allowed: bool
    autonomy_level: str
    require_human: bool
    reason: str
    rights_used: List[str] = field(default_factory=list)
    escalation_triggers: List[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def list_autonomy_levels() -> List[Dict[str, Any]]:
    return [dict(item) for item in AUTONOMY_LEVELS]


def normalize_autonomy_level(level: Optional[str]) -> str:
    if not level:
        return DEFAULT_AUTONOMY_LEVEL
    value = str(level).strip().upper()
    if value in _LEVEL_BY_ID:
        return value
    aliases = {
        "SUPERVISED": "L0",
        "ASSISTED": "L1",
        "CONDITIONAL": "L2",
        "HIGH": "L3",
        "FULL": "L4",
        "0": "L0",
        "1": "L1",
        "2": "L2",
        "3": "L3",
        "4": "L4",
    }
    return aliases.get(value, DEFAULT_AUTONOMY_LEVEL)


def get_autonomy_profile(level: Optional[str]) -> Dict[str, Any]:
    normalized = normalize_autonomy_level(level)
    return dict(_LEVEL_BY_ID[normalized])


def risk_rank(risk: Optional[str]) -> int:
    return _RISK_RANK.get(str(risk or "medium").lower(), 2)


def max_task_risk(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return "low"
    ranked = sorted(
        tasks,
        key=lambda task: risk_rank(task.get("risk_level")),
        reverse=True,
    )
    return str(ranked[0].get("risk_level") or "medium").lower()


def decision_rights_for(level: Optional[str]) -> Dict[str, bool]:
    """Map standard rights to allow/deny under the selected autonomy level."""
    profile = get_autonomy_profile(level)
    lid = profile["id"]
    rights = {name: True for name in AUTONOMY_DECISION_RIGHTS}

    if lid == "L0":
        rights["plan_execute"] = False
        rights["review_self_approve"] = False
        rights["final_release"] = False
    elif lid == "L1":
        rights["plan_execute"] = False
        rights["final_release"] = False
    elif lid == "L2":
        rights["review_self_approve"] = True
        rights["final_release"] = True
    elif lid == "L3":
        rights["review_self_approve"] = True
        rights["final_release"] = True
    else:  # L4
        rights["plan_execute"] = True
        rights["review_self_approve"] = True
        rights["final_release"] = True
    return rights


class AutonomyGovernor:
    """Evaluates whether agents may proceed autonomously or must escalate."""

    def __init__(self, autonomy_level: Optional[str] = None):
        self.level = normalize_autonomy_level(autonomy_level)
        self.profile = get_autonomy_profile(self.level)
        self.rights = decision_rights_for(self.level)
        self.decisions: List[GovernanceDecision] = []

    def catalog(self) -> Dict[str, Any]:
        return {
            "framework": GOVERNANCE_FRAMEWORK_NAME,
            "version": GOVERNANCE_FRAMEWORK_VERSION,
            "selected_level": self.level,
            "profile": self.profile,
            "rights": self.rights,
            "levels": list_autonomy_levels(),
        }

    def _record(self, decision: GovernanceDecision) -> GovernanceDecision:
        self.decisions.append(decision)
        return decision

    def evaluate_plan_gate(self, plan: Dict[str, Any] | None) -> GovernanceDecision:
        tasks = (plan or {}).get("tasks") or []
        plan_risk = max_task_risk(tasks)
        triggers: List[str] = []
        require_human = bool(self.profile.get("requires_plan_approval"))

        ceiling = self.profile.get("max_autonomous_risk")
        if ceiling is not None and risk_rank(plan_risk) > risk_rank(ceiling):
            require_human = True
            triggers.append(
                f"plan_risk:{plan_risk} exceeds autonomy ceiling:{ceiling}"
            )

        if not self.rights.get("plan_execute", True):
            require_human = True
            triggers.append("right:plan_execute=denied")

        decision = GovernanceDecision(
            action="plan_execute",
            allowed=True,
            autonomy_level=self.level,
            require_human=require_human,
            reason=(
                "Plan requires human approval under autonomy policy"
                if require_human
                else "Plan may execute autonomously"
            ),
            rights_used=["plan_execute"],
            escalation_triggers=triggers,
        )
        return self._record(decision)

    def evaluate_review_gate(
        self,
        *,
        task: Dict[str, Any],
        review: Dict[str, Any],
        policy_violations: Optional[List[str]] = None,
        pending_remaining: bool = False,
    ) -> GovernanceDecision:
        violations = list(policy_violations or [])
        approved = bool(review.get("approved"))
        score = int(review.get("score") or 0)
        task_risk = str(task.get("risk_level") or "medium").lower()
        triggers: List[str] = []
        require_human = False

        if self.profile.get("requires_review_approval"):
            require_human = True
            triggers.append("policy:requires_review_approval")

        if (
            not approved
            and self.profile.get("auto_escalate_on_reject")
            and self.level in {"L0", "L1", "L2"}
        ):
            require_human = True
            triggers.append("review:rejected")

        if violations:
            require_human = True
            triggers.append(f"policy_violations:{len(violations)}")

        ceiling = self.profile.get("max_autonomous_risk")
        if ceiling is not None and risk_rank(task_risk) > risk_rank(ceiling):
            require_human = True
            triggers.append(f"task_risk:{task_risk} exceeds ceiling:{ceiling}")

        if task_risk == "critical" and self.level != "L4":
            require_human = True
            triggers.append("risk:critical")

        if not approved and score < MIN_REVIEW_SCORE and self.level in {"L3"}:
            require_human = True
            triggers.append(f"severe_quality_miss:score={score}")

        if self.level == "L4":
            # Full autonomy: still block only on hard policy violations via separate gate;
            # do not open human interrupt unless explicitly forced by caller.
            require_human = False
            triggers = [t for t in triggers if t.startswith("policy_violations")]
            if triggers:
                # Hard fail remains non-autonomous continuation but without HITL interrupt
                # — caller should keep status needs_review / fail closed.
                require_human = False

        # Final release gate when no pending work remains
        if (
            approved
            and not pending_remaining
            and self.profile.get("requires_final_release")
        ):
            require_human = True
            triggers.append("policy:requires_final_release")

        if not self.rights.get("review_self_approve", True) and approved:
            # L0 must still confirm even successful reviews
            require_human = True
            if "policy:requires_review_approval" not in triggers:
                triggers.append("right:review_self_approve=denied")

        decision = GovernanceDecision(
            action="review_continue",
            allowed=True,
            autonomy_level=self.level,
            require_human=require_human,
            reason=(
                "Human governance gate required"
                if require_human
                else "Review may continue autonomously"
            ),
            rights_used=["review_self_approve", "final_release"],
            escalation_triggers=triggers,
        )
        return self._record(decision)

    def summary(self) -> Dict[str, Any]:
        return {
            "framework": GOVERNANCE_FRAMEWORK_NAME,
            "version": GOVERNANCE_FRAMEWORK_VERSION,
            "autonomy_level": self.level,
            "profile": self.profile,
            "rights": self.rights,
            "decisions": [item.to_dict() for item in self.decisions],
            "escalations": sum(1 for item in self.decisions if item.require_human),
        }
