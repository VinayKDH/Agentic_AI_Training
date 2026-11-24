"""Enterprise reviewer with structured approval and policy-aware scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import Task, TaskStatus
from utils.constants import (
    ENTERPRISE_POLICY_CHECKLIST,
    MIN_APPROVAL_SCORE,
    REVIEW_TEMPERATURE,
    REVIEWER_SYSTEM_PROMPT,
)
from utils.guardrails import sanitize_for_prompt
from utils.llm import get_llm
from utils.resilience import with_retry


class ReviewDecision(BaseModel):
    decision: Literal["approve", "needs_revision"] = Field(
        description="Whether the work product is approved"
    )
    score: int = Field(ge=1, le=10, description="Quality score from 1-10")
    feedback: str = Field(description="Detailed constructive feedback")
    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete improvements if revision is needed",
    )
    security_findings: list[str] = Field(
        default_factory=list,
        description="Security or compliance findings",
    )
    residual_risks: list[str] = Field(
        default_factory=list,
        description="Accepted residual risks if approved",
    )


class ReviewerAgent:
    def __init__(self):
        self.llm = get_llm(temperature=REVIEW_TEMPERATURE).with_structured_output(
            ReviewDecision
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", REVIEWER_SYSTEM_PROMPT),
                (
                    "human",
                    "Original Task: {task_description}\n\n"
                    "Acceptance criteria:\n{acceptance}\n\n"
                    "Risk level: {risk_level} | Priority: {priority}\n\n"
                    "Enterprise checklist:\n{checklist}\n\n"
                    "Work Product:\n{work_product}\n\n"
                    "Deterministic policy notes:\n{policy_notes}\n\n"
                    "Context:\n{context}\n\n"
                    "Provide a strict enterprise quality review.",
                ),
            ]
        )

    def review(
        self,
        task: Task,
        work_product: dict,
        context: dict | None = None,
        policy_notes: str = "",
    ) -> dict:
        """Review a work product and return a structured enterprise decision."""
        acceptance = "\n".join(
            f"- {item}" for item in (task.get("acceptance_criteria") or [])
        ) or "- Meets task description"
        checklist = "\n".join(f"- {item}" for item in ENTERPRISE_POLICY_CHECKLIST)
        context_str = sanitize_for_prompt(str(context) if context else "No additional context")

        if "code" in work_product:
            work_product_str = (
                f"Code ({work_product.get('language', 'unknown')}):\n"
                f"{work_product.get('code', '')}\n\n"
                f"Explanation:\n{work_product.get('explanation', '')}\n\n"
                f"Usage:\n{work_product.get('usage', '')}\n\n"
                f"Security notes:\n{work_product.get('security_notes', '')}"
            )
        else:
            work_product_str = (
                f"Research Findings:\n{work_product.get('findings', '')}\n\n"
                f"Sources: {work_product.get('sources', [])}"
            )
        work_product_str = sanitize_for_prompt(work_product_str, 10000)

        try:
            decision: ReviewDecision = with_retry(
                lambda: (self.prompt | self.llm).invoke(
                    {
                        "task_description": task["description"],
                        "acceptance": acceptance,
                        "risk_level": task.get("risk_level", "medium"),
                        "priority": task.get("priority", "p1"),
                        "checklist": checklist,
                        "work_product": work_product_str,
                        "policy_notes": policy_notes or "None",
                        "context": context_str,
                    }
                ),
                operation="reviewer.review",
            )
            threshold = MIN_APPROVAL_SCORE
            if task.get("risk_level") in {"high", "critical"}:
                threshold = max(threshold, 9)

            approved = decision.decision == "approve" and decision.score >= threshold
            feedback = decision.feedback
            extras: list[str] = []
            if decision.improvement_suggestions:
                extras.append(
                    "Suggestions:\n- " + "\n- ".join(decision.improvement_suggestions)
                )
            if decision.security_findings:
                extras.append(
                    "Security findings:\n- " + "\n- ".join(decision.security_findings)
                )
            if decision.residual_risks:
                extras.append(
                    "Residual risks:\n- " + "\n- ".join(decision.residual_risks)
                )
            if extras:
                feedback = f"{feedback}\n\n" + "\n\n".join(extras)

            return {
                "task_id": task["id"],
                "approved": approved,
                "score": decision.score,
                "decision": "approve" if approved else "needs_revision",
                "feedback": feedback,
                "security_findings": decision.security_findings,
                "residual_risks": decision.residual_risks,
                "threshold": threshold,
                "status": (
                    TaskStatus.COMPLETED if approved else TaskStatus.NEEDS_REVIEW
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "task_id": task["id"],
                "approved": False,
                "score": 1,
                "decision": "needs_revision",
                "feedback": f"Review error: {exc}",
                "security_findings": [],
                "residual_risks": ["Reviewer unavailable"],
                "threshold": MIN_APPROVAL_SCORE,
                "status": TaskStatus.FAILED,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
