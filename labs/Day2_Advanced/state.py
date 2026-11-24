"""LangGraph state schema for the Day2 Advanced enterprise multi-agent system."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentRole(str, Enum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class Task(TypedDict, total=False):
    id: str
    description: str
    assigned_to: AgentRole
    status: TaskStatus
    result: Optional[str]
    dependencies: List[str]
    acceptance_criteria: List[str]
    risk_level: str
    priority: str
    created_at: str
    completed_at: Optional[str]


def merge_dicts(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Append-only reducer for artifact lists."""
    return (left or []) + (right or [])


def merge_strings(left: List[str], right: List[str]) -> List[str]:
    return (left or []) + (right or [])


def upsert_tasks(existing: List[Task], updates: List[Task]) -> List[Task]:
    """Merge task updates by id while preserving order."""
    if not updates:
        return existing or []

    by_id: Dict[str, Task] = {task["id"]: task for task in (existing or [])}
    order = [task["id"] for task in (existing or [])]

    for task in updates:
        task_id = task["id"]
        if task_id in by_id:
            by_id[task_id] = {**by_id[task_id], **task}
        else:
            by_id[task_id] = task
            order.append(task_id)

    return [by_id[task_id] for task_id in order]


class MultiAgentState(TypedDict, total=False):
    """Shared graph state with reducers for concurrent/parallel updates."""

    messages: Annotated[List[BaseMessage], add_messages]
    original_query: str
    plan: Optional[Dict[str, Any]]
    tasks: Annotated[List[Task], upsert_tasks]
    current_task_id: Optional[str]
    research_findings: Annotated[List[Dict[str, Any]], merge_dicts]
    code_artifacts: Annotated[List[Dict[str, Any]], merge_dicts]
    review_feedback: Annotated[List[Dict[str, Any]], merge_dicts]
    final_output: str
    iteration_count: int
    agent_history: Annotated[List[Dict[str, Any]], merge_dicts]
    errors: Annotated[List[str], merge_strings]
    policy_violations: Annotated[List[str], merge_strings]
    requires_human_input: bool
    human_feedback: Optional[str]
    run_id: str
    run_metadata: Dict[str, Any]
    metrics: Dict[str, Any]
    compliance: Dict[str, Any]
    guardrail_status: Dict[str, Any]
    autonomy_level: str
    governance: Dict[str, Any]
    governance_decisions: Annotated[List[Dict[str, Any]], merge_dicts]
