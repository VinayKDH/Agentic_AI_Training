"""Reviewer agent with structured approval decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import Task, TaskStatus
from utils.constants import REVIEW_TEMPERATURE, REVIEWER_SYSTEM_PROMPT
from utils.llm import get_llm


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
                    "Work Product:\n{work_product}\n\n"
                    "Context:\n{context}\n\n"
                    "Provide a strict quality review.",
                ),
            ]
        )

    def review(
        self,
        task: Task,
        work_product: dict,
        context: dict | None = None,
    ) -> dict:
        """Review a work product and return a structured decision."""
        context_str = str(context) if context else "No additional context"
        if "code" in work_product:
            work_product_str = (
                f"Code ({work_product.get('language', 'unknown')}):\n"
                f"{work_product.get('code', '')}\n\n"
                f"Explanation:\n{work_product.get('explanation', '')}\n\n"
                f"Usage:\n{work_product.get('usage', '')}"
            )
        else:
            work_product_str = (
                f"Research Findings:\n{work_product.get('findings', '')}"
            )

        try:
            decision: ReviewDecision = (self.prompt | self.llm).invoke(
                {
                    "task_description": task["description"],
                    "work_product": work_product_str,
                    "context": context_str,
                }
            )
            approved = decision.decision == "approve" and decision.score >= 7
            feedback = decision.feedback
            if decision.improvement_suggestions:
                feedback = (
                    f"{feedback}\n\nSuggestions:\n- "
                    + "\n- ".join(decision.improvement_suggestions)
                )

            return {
                "task_id": task["id"],
                "approved": approved,
                "score": decision.score,
                "decision": decision.decision,
                "feedback": feedback,
                "status": (
                    TaskStatus.COMPLETED if approved else TaskStatus.NEEDS_REVIEW
                ),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {
                "task_id": task["id"],
                "approved": False,
                "score": 1,
                "decision": "needs_revision",
                "feedback": f"Review error: {exc}",
                "status": TaskStatus.FAILED,
                "timestamp": datetime.now().isoformat(),
            }
