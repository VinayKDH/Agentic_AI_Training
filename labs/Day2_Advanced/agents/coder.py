"""Coder agent with structured code generation."""

from __future__ import annotations

import re
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import Task, TaskStatus
from utils.constants import CODER_SYSTEM_PROMPT, CODER_TEMPERATURE
from utils.llm import get_llm


class CodeArtifact(BaseModel):
    code: str = Field(description="Complete source code")
    language: str = Field(default="python", description="Programming language")
    explanation: str = Field(description="Brief explanation of the solution")
    usage: str = Field(default="", description="How to run or use the code")


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
                    "Context/Requirements:\n{context}\n\n"
                    "Generate complete, runnable code with explanation and usage notes.",
                ),
            ]
        )

    def generate_code(self, task: Task, context: dict | None = None) -> dict:
        """Generate structured code for a task."""
        context_str = ""
        if context:
            context_str = (
                f"Research findings:\n{context.get('research', '')}\n\n"
                f"Previous code:\n{context.get('code', '')}\n\n"
                f"Review feedback:\n{context.get('reviews', '')}"
            )

        try:
            result: CodeArtifact = (self.prompt | self.llm).invoke(
                {
                    "task_description": task["description"],
                    "context": context_str or "No prior context.",
                }
            )
            return {
                "task_id": task["id"],
                "code": result.code,
                "language": result.language,
                "explanation": result.explanation,
                "usage": result.usage,
                "status": TaskStatus.COMPLETED,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            # Fallback to free-form generation if structured output fails
            try:
                from utils.llm import get_llm as _get_llm

                raw = (
                    ChatPromptTemplate.from_messages(
                        [
                            ("system", CODER_SYSTEM_PROMPT),
                            (
                                "human",
                                "Task: {task_description}\n\nContext:\n{context}",
                            ),
                        ]
                    )
                    | _get_llm(temperature=CODER_TEMPERATURE)
                ).invoke(
                    {
                        "task_description": task["description"],
                        "context": context_str or "No prior context.",
                    }
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
                    "usage": "",
                    "status": TaskStatus.COMPLETED,
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as nested:
                return {
                    "task_id": task["id"],
                    "code": "",
                    "language": "python",
                    "explanation": f"Code generation error: {exc}; fallback: {nested}",
                    "usage": "",
                    "status": TaskStatus.FAILED,
                    "timestamp": datetime.now().isoformat(),
                }
