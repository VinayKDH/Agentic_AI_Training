"""Routing helpers for Command/Send based multi-agent control flow."""

from __future__ import annotations

from typing import List

from state import AgentRole, MultiAgentState, Task, TaskStatus
from utils.constants import MAX_REVIEW_LOOPS


def pending_tasks(
    tasks: List[Task],
    role: AgentRole | None = None,
) -> List[Task]:
    statuses = {TaskStatus.PENDING, TaskStatus.NEEDS_REVIEW}
    result = [task for task in tasks if task.get("status") in statuses]
    if role is not None:
        result = [task for task in result if task.get("assigned_to") == role]
    return result


def next_route_after_plan(state: MultiAgentState) -> str:
    tasks = state.get("tasks", [])
    if pending_tasks(tasks, AgentRole.RESEARCHER):
        return "researcher"
    if pending_tasks(tasks, AgentRole.CODER):
        return "coder"
    return "synthesizer"


def next_route_after_review(state: MultiAgentState) -> str:
    if int(state.get("iteration_count") or 0) >= MAX_REVIEW_LOOPS:
        return "synthesizer"

    current_task_id = state.get("current_task_id")
    tasks = state.get("tasks", [])
    if not current_task_id:
        return "synthesizer"

    task = next((item for item in tasks if item.get("id") == current_task_id), None)
    reviews = state.get("review_feedback", [])
    latest = next(
        (review for review in reversed(reviews) if review.get("task_id") == current_task_id),
        None,
    )

    if latest and latest.get("approved"):
        if pending_tasks(tasks, AgentRole.CODER):
            return "coder"
        if pending_tasks(tasks, AgentRole.RESEARCHER):
            return "researcher"
        return "synthesizer"

    if task and task.get("assigned_to") == AgentRole.CODER:
        return "coder"
    if task and task.get("assigned_to") == AgentRole.RESEARCHER:
        return "researcher"
    return "synthesizer"
