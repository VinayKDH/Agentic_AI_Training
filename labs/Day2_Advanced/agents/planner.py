"""Enterprise planner agent with structured output, risk, and acceptance criteria."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import AgentRole, Task, TaskStatus
from utils.constants import (
    ENTERPRISE_POLICY_CHECKLIST,
    MAX_PLAN_TASKS,
    PLANNER_SYSTEM_PROMPT,
    PLANNER_TEMPERATURE,
)
from utils.llm import get_llm
from utils.resilience import with_retry


class PlannedTask(BaseModel):
    description: str = Field(description="Actionable task description")
    agent: Literal["researcher", "coder"] = Field(
        description="Worker agent assigned to this task"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Optional dependency labels or prior task descriptions",
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="Testable acceptance criteria for enterprise handoff",
    )
    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Delivery/security risk level",
    )
    priority: Literal["p0", "p1", "p2", "p3"] = Field(
        default="p1",
        description="Business priority",
    )


class TaskPlan(BaseModel):
    tasks: List[PlannedTask] = Field(description="Ordered execution plan")
    reasoning: str = Field(description="Why this plan solves the user request")
    delivery_notes: str = Field(
        default="",
        description="Enterprise delivery notes, assumptions, and constraints",
    )


class PlannerAgent:
    def __init__(self):
        self.llm = get_llm(temperature=PLANNER_TEMPERATURE).with_structured_output(
            TaskPlan
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_SYSTEM_PROMPT.format(max_tasks=MAX_PLAN_TASKS)),
                (
                    "human",
                    "User Query: {query}\n\n"
                    "Enterprise policy checklist:\n{checklist}\n\n"
                    "Create a compact enterprise delivery plan with acceptance criteria, "
                    "risk, and priority on each task.",
                ),
            ]
        )

    def create_plan(self, query: str) -> dict:
        """Create a structured enterprise execution plan from the user query."""
        checklist = "\n".join(f"- {item}" for item in ENTERPRISE_POLICY_CHECKLIST)
        try:
            result: TaskPlan = with_retry(
                lambda: (self.prompt | self.llm).invoke(
                    {"query": query, "checklist": checklist}
                ),
                operation="planner.create_plan",
            )
            tasks: List[Task] = []
            for planned in result.tasks[:MAX_PLAN_TASKS]:
                criteria = planned.acceptance_criteria or [
                    "Meets stated task description",
                    "Passes enterprise reviewer quality gate",
                ]
                tasks.append(
                    Task(
                        id=str(uuid.uuid4()),
                        description=planned.description,
                        assigned_to=AgentRole(planned.agent),
                        status=TaskStatus.PENDING,
                        result=None,
                        dependencies=planned.dependencies,
                        acceptance_criteria=criteria,
                        risk_level=planned.risk_level,
                        priority=planned.priority,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        completed_at=None,
                    )
                )
            return {
                "tasks": tasks,
                "reasoning": result.reasoning,
                "delivery_notes": result.delivery_notes,
                "plan_structure": [task["description"] for task in tasks],
            }
        except Exception as exc:  # noqa: BLE001
            fallback_tasks: List[Task] = [
                Task(
                    id=str(uuid.uuid4()),
                    description=f"Research enterprise-ready approach for: {query}",
                    assigned_to=AgentRole.RESEARCHER,
                    status=TaskStatus.PENDING,
                    result=None,
                    dependencies=[],
                    acceptance_criteria=[
                        "Findings include sources or explicit unknowns",
                        "Risks and constraints are listed",
                    ],
                    risk_level="medium",
                    priority="p1",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    completed_at=None,
                ),
                Task(
                    id=str(uuid.uuid4()),
                    description=f"Implement a secure, runnable solution for: {query}",
                    assigned_to=AgentRole.CODER,
                    status=TaskStatus.PENDING,
                    result=None,
                    dependencies=[],
                    acceptance_criteria=[
                        "Code is runnable with usage notes",
                        "No secrets; basic validation/error handling included",
                    ],
                    risk_level="medium",
                    priority="p1",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    completed_at=None,
                ),
            ]
            return {
                "tasks": fallback_tasks,
                "reasoning": (
                    f"LLM planning failed ({exc}); used deterministic "
                    "researcher+coder enterprise fallback."
                ),
                "delivery_notes": "Fallback plan applied due to planner failure.",
                "plan_structure": [task["description"] for task in fallback_tasks],
            }
