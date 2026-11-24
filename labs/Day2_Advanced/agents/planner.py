"""Planner agent with structured output."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import AgentRole, Task, TaskStatus
from utils.constants import MAX_PLAN_TASKS, PLANNER_SYSTEM_PROMPT
from utils.llm import get_llm


class PlannedTask(BaseModel):
    description: str = Field(description="Actionable task description")
    agent: Literal["researcher", "coder"] = Field(
        description="Worker agent assigned to this task"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Optional dependency labels or prior task descriptions",
    )


class TaskPlan(BaseModel):
    tasks: List[PlannedTask] = Field(description="Ordered execution plan")
    reasoning: str = Field(description="Why this plan solves the user request")


class PlannerAgent:
    def __init__(self):
        self.llm = get_llm(temperature=0.2).with_structured_output(TaskPlan)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_SYSTEM_PROMPT.format(max_tasks=MAX_PLAN_TASKS)),
                (
                    "human",
                    "User Query: {query}\n\nCreate a detailed but compact plan.",
                ),
            ]
        )

    def create_plan(self, query: str) -> dict:
        """Create a structured execution plan from the user query."""
        try:
            result: TaskPlan = (self.prompt | self.llm).invoke({"query": query})
            tasks: List[Task] = []
            for planned in result.tasks[:MAX_PLAN_TASKS]:
                tasks.append(
                    Task(
                        id=str(uuid.uuid4()),
                        description=planned.description,
                        assigned_to=AgentRole(planned.agent),
                        status=TaskStatus.PENDING,
                        result=None,
                        dependencies=planned.dependencies,
                        created_at=datetime.now().isoformat(),
                        completed_at=None,
                    )
                )
            return {
                "tasks": tasks,
                "reasoning": result.reasoning,
                "plan_structure": [task["description"] for task in tasks],
            }
        except Exception as exc:
            # Deterministic fallback keeps the graph demoable when the LLM is unavailable
            fallback_tasks: List[Task] = [
                Task(
                    id=str(uuid.uuid4()),
                    description=f"Research best practices related to: {query}",
                    assigned_to=AgentRole.RESEARCHER,
                    status=TaskStatus.PENDING,
                    result=None,
                    dependencies=[],
                    created_at=datetime.now().isoformat(),
                    completed_at=None,
                ),
                Task(
                    id=str(uuid.uuid4()),
                    description=f"Implement a practical solution for: {query}",
                    assigned_to=AgentRole.CODER,
                    status=TaskStatus.PENDING,
                    result=None,
                    dependencies=[],
                    created_at=datetime.now().isoformat(),
                    completed_at=None,
                ),
            ]
            return {
                "tasks": fallback_tasks,
                "reasoning": (
                    f"LLM planning failed ({exc}); used deterministic researcher+coder fallback."
                ),
                "plan_structure": [task["description"] for task in fallback_tasks],
            }
