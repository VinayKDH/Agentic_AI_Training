"""Enterprise coder agent with structured, security-aware code generation."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import Task, TaskStatus
from utils.constants import (
    CODER_SYSTEM_PROMPT,
    CODER_TEMPERATURE,
    ENTERPRISE_POLICY_CHECKLIST,
)
from utils.guardrails import sanitize_for_prompt
from utils.llm import get_llm
from utils.resilience import with_retry


class CodeArtifact(BaseModel):
    code: str = Field(description="Complete source code")
    language: str = Field(default="python", description="Programming language")
    explanation: str = Field(description="Brief explanation of the solution")
    usage: str = Field(description="How to run, configure, and test the code")
    security_notes: str = Field(
        default="",
        description="Security considerations and residual risks",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Required packages or services",
    )


class CoderAgent:
    def __init__(self):
        self.llm = get_llm(temperature=CODER_TEMPERATURE).with_structured_output(
            CodeArtifact
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CODER_SYSTEM_PROMPT),
                (
                    "human",
                    "Task: {task_description}\n\n"
                    "Acceptance criteria:\n{acceptance}\n\n"
                    "Risk level: {risk_level} | Priority: {priority}\n\n"
                    "Enterprise checklist:\n{checklist}\n\n"
                    "Context/Requirements:\n{context}\n\n"
                    "Generate complete, secure, runnable code with usage and security notes.",
                ),
            ]
        )

    def generate_code(self, task: Task, context: dict | None = None) -> dict:
        """Generate structured enterprise code for a task."""
        acceptance = "\n".join(
            f"- {item}" for item in (task.get("acceptance_criteria") or [])
        ) or "- Runnable solution with usage notes"
        checklist = "\n".join(f"- {item}" for item in ENTERPRISE_POLICY_CHECKLIST)
        context_str = ""
        if context:
            context_str = (
                f"Research findings:\n{sanitize_for_prompt(context.get('research', ''), 2500)}\n\n"
                f"Previous code:\n{sanitize_for_prompt(context.get('code', ''), 1500)}\n\n"
                f"Review feedback:\n{sanitize_for_prompt(context.get('reviews', ''), 1500)}"
            )

        invoke_args = {
            "task_description": task["description"],
            "acceptance": acceptance,
            "risk_level": task.get("risk_level", "medium"),
            "priority": task.get("priority", "p1"),
            "checklist": checklist,
            "context": context_str or "No prior context.",
        }

        try:
            result: CodeArtifact = with_retry(
                lambda: (self.prompt | self.llm).invoke(invoke_args),
                operation="coder.generate",
            )
            return {
                "task_id": task["id"],
                "code": result.code,
                "language": result.language,
                "explanation": result.explanation,
                "usage": result.usage,
                "security_notes": result.security_notes,
                "dependencies": result.dependencies,
                "status": TaskStatus.COMPLETED,
                "risk_level": task.get("risk_level", "medium"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            try:
                raw = with_retry(
                    lambda: (
                        ChatPromptTemplate.from_messages(
                            [
                                ("system", CODER_SYSTEM_PROMPT),
                                (
                                    "human",
                                    "Task: {task_description}\n\n"
                                    "Acceptance:\n{acceptance}\n\n"
                                    "Context:\n{context}",
                                ),
                            ]
                        )
                        | get_llm(temperature=CODER_TEMPERATURE)
                    ).invoke(
                        {
                            "task_description": task["description"],
                            "acceptance": acceptance,
                            "context": context_str or "No prior context.",
                        }
                    ),
                    operation="coder.fallback",
                )
                content = raw.content
                blocks = re.findall(
                    r"```(?:python|javascript|typescript|java|go|rust)?\n(.*?)```",
                    content,
                    re.DOTALL,
                )
                return {
                    "task_id": task["id"],
                    "code": blocks[0] if blocks else content,
                    "language": "python",
                    "explanation": re.sub(
                        r"```.*?```", "", content, flags=re.DOTALL
                    ).strip(),
                    "usage": "See explanation for run steps.",
                    "security_notes": f"Fallback generation used after: {exc}",
                    "dependencies": [],
                    "status": TaskStatus.COMPLETED,
                    "risk_level": task.get("risk_level", "medium"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as nested:  # noqa: BLE001
                return {
                    "task_id": task["id"],
                    "code": "",
                    "language": "python",
                    "explanation": f"Code generation error: {exc}; fallback: {nested}",
                    "usage": "",
                    "security_notes": "Generation failed",
                    "dependencies": [],
                    "status": TaskStatus.FAILED,
                    "risk_level": task.get("risk_level", "medium"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
