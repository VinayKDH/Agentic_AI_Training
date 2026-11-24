"""JSON-safe serializers for LangGraph state and SSE events."""

from __future__ import annotations

from enum import Enum
from typing import Any


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if hasattr(value, "content"):
        return {"type": value.__class__.__name__, "content": str(value.content)}
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump())
    return str(value)


def summarize_state(state: dict) -> dict:
    tasks = to_jsonable(state.get("tasks") or [])
    return {
        "run_id": state.get("run_id"),
        "final_output": state.get("final_output") or "",
        "tasks": tasks,
        "research_findings": to_jsonable(state.get("research_findings") or []),
        "code_artifacts": to_jsonable(state.get("code_artifacts") or []),
        "review_feedback": to_jsonable(state.get("review_feedback") or []),
        "metrics": to_jsonable(state.get("metrics") or {}),
        "compliance": to_jsonable(state.get("compliance") or {}),
        "policy_violations": to_jsonable(state.get("policy_violations") or []),
        "run_metadata": to_jsonable(state.get("run_metadata") or {}),
        "guardrail_status": to_jsonable(state.get("guardrail_status") or {}),
    }
