"""Routing helpers for Command-based enterprise multi-agent control flow."""

from __future__ import annotations

from typing import List

from state import AgentRole, MultiAgentState, Task, TaskStatus
from utils.constants import MAX_REVIEW_LOOPS


def _status_value(status) -> str:
    return getattr(status, "value", status)


def _role_value(role) -> str:
    return getattr(role, "value", role)


def dependencies_met(task: Task, tasks: List[Task]) -> bool:
    deps = task.get("dependencies") or []
    if not deps:
        return True
    by_id = {item.get("id"): item for item in tasks}
    descriptions = {
        (item.get("description") or "").strip().lower(): item for item in tasks
    }
    for dep in deps:
        key = str(dep).strip()
        target = by_id.get(key) or descriptions.get(key.lower())
        if not target:
            # Unknown dependency label — do not hard-block
            continue
        if _status_value(target.get("status")) != TaskStatus.COMPLETED.value:
            return False
    return True


def pending_tasks(
    tasks: List[Task],
    role: AgentRole | None = None,
    *,
    respect_dependencies: bool = True,
) -> List[Task]:
    statuses = {
        TaskStatus.PENDING.value,
        TaskStatus.NEEDS_REVIEW.value,
    }
    result = [
        task
        for task in tasks
        if _status_value(task.get("status")) in statuses
    ]
    if role is not None:
        role_val = _role_value(role)
        result = [
            task
            for task in result
            if _role_value(task.get("assigned_to")) == role_val
        ]
    if respect_dependencies:
        result = [task for task in result if dependencies_met(task, tasks)]
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
        (
            review
            for review in reversed(reviews)
            if review.get("task_id") == current_task_id
        ),
        None,
    )

    if latest and latest.get("approved"):
        if pending_tasks(tasks, AgentRole.CODER):
            return "coder"
        if pending_tasks(tasks, AgentRole.RESEARCHER):
            return "researcher"
        return "synthesizer"

    if task and _role_value(task.get("assigned_to")) == AgentRole.CODER.value:
        return "coder"
    if task and _role_value(task.get("assigned_to")) == AgentRole.RESEARCHER.value:
        return "researcher"
    return "synthesizer"
