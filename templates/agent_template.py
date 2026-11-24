"""
Reusable Agent Template
=======================
Copy this file into a lab's `agents/` folder and rename it.

Pattern used in Day2 Advanced:
  agents/planner.py | researcher.py | coder.py | reviewer.py

Student steps:
  1. Rename MyAgent / MyAgentOutput / MY_AGENT_* placeholders
  2. Move prompts & temperature into utils/constants.py
  3. Implement `run()` (or a domain method like create_plan / research)
  4. Wire the agent into a LangGraph node in graph/*.py

Dependencies expected in the lab:
  - utils.llm.get_llm
  - utils.resilience.with_retry   (optional but recommended)
  - utils.constants              (put prompts here)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# --- Lab imports (adjust paths if your lab layout differs) ---
# from state import Task, TaskStatus
# from utils.constants import MY_AGENT_SYSTEM_PROMPT, MY_AGENT_TEMPERATURE
# from utils.llm import get_llm
# from utils.resilience import with_retry


# =============================================================================
# 1) Structured output schema (what the LLM must return)
# =============================================================================
class MyAgentOutput(BaseModel):
    """Replace fields with what THIS agent must produce."""

    summary: str = Field(description="Short summary of the work done")
    details: str = Field(description="Full actionable output for downstream nodes")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Self-reported confidence from 0 to 1",
    )


# =============================================================================
# 2) Prompts / config — MOVE THESE TO utils/constants.py in real labs
# =============================================================================
MY_AGENT_TEMPERATURE = 0.2

MY_AGENT_SYSTEM_PROMPT = """You are a specialized agent with ONE clear job.
Follow the task instructions exactly.
Be concise, accurate, and explicit about assumptions.
Never invent credentials, private data, or unsupported facts.
"""


# =============================================================================
# 3) Agent class
# =============================================================================
class MyAgent:
    """
    Template agent.

    Responsibilities:
      - Build prompt + LLM chain
      - Execute the agent job for one task
      - Return a plain dict the graph node can merge into state

    Non-responsibilities (leave to the graph):
      - Routing to the next node
      - Checkpointing / HITL interrupt
      - Merging full MultiAgentState
    """

    def __init__(self, temperature: float = MY_AGENT_TEMPERATURE):
        # In a real lab:
        #   self.llm = get_llm(temperature=temperature).with_structured_output(MyAgentOutput)
        #
        # Kept as a placeholder so this template file is readable without importing lab modules.
        self.temperature = temperature
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", MY_AGENT_SYSTEM_PROMPT),
                (
                    "human",
                    "Task:\n{task_description}\n\n"
                    "Acceptance criteria:\n{acceptance}\n\n"
                    "Context from previous agents:\n{context}\n\n"
                    "Produce the structured result for this task.",
                ),
            ]
        )
        # self.chain = self.prompt | self.llm

    def run(
        self,
        task: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute the agent for one task.

        Args:
            task: Task dict from graph state. Expected keys often include:
                  id, description, acceptance_criteria, risk_level, priority, status
            context: Optional shared context from prior nodes, e.g.
                  {"research": "...", "code": "...", "reviews": "..."}

        Returns:
            Plain dict suitable for graph state updates.
        """
        acceptance = "\n".join(
            f"- {item}" for item in (task.get("acceptance_criteria") or [])
        ) or "- Complete the task as described"

        context_str = "No prior context."
        if context:
            parts = [f"{key}: {value}" for key, value in context.items() if value]
            context_str = "\n".join(parts) if parts else context_str

        invoke_args = {
            "task_description": task.get("description", ""),
            "acceptance": acceptance,
            "context": context_str,
        }

        try:
            # --- Real lab pattern (uncomment when wired) ---
            # result: MyAgentOutput = with_retry(
            #     lambda: self.chain.invoke(invoke_args),
            #     operation="my_agent.run",
            # )
            # return {
            #     "task_id": task.get("id"),
            #     "output": result.details,
            #     "summary": result.summary,
            #     "confidence": result.confidence,
            #     "status": "completed",  # or TaskStatus.COMPLETED
            #     "timestamp": datetime.now(timezone.utc).isoformat(),
            # }

            # --- Template placeholder (shows expected shape) ---
            _ = invoke_args  # silence unused warning in template
            return {
                "task_id": task.get("id"),
                "output": "Replace this with LLM structured output.",
                "summary": "Template placeholder — implement LLM call.",
                "confidence": 0.0,
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:  # noqa: BLE001 - boundary for agent fallback
            return {
                "task_id": task.get("id"),
                "output": "",
                "summary": f"Agent failed: {exc}",
                "confidence": 0.0,
                "status": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }


# =============================================================================
# 4) Optional: tool-using agent variant (see Day2 researcher)
# =============================================================================
#
# from langchain.agents import create_agent
# from langchain_core.messages import HumanMessage
#
# class MyToolAgent:
#     def __init__(self):
#         self.llm = get_llm(temperature=0.3)
#         self.tools = [...]  # e.g. web_search
#         self.agent = create_agent(
#             model=self.llm,
#             tools=self.tools,
#             system_prompt=MY_AGENT_SYSTEM_PROMPT,
#         )
#
#     def run(self, task: dict, context: dict | None = None) -> dict:
#         result = self.agent.invoke({"messages": [HumanMessage(content=task["description"])]})
#         messages = result.get("messages", [])
#         output = messages[-1].content if messages else str(result)
#         return {
#             "task_id": task["id"],
#             "output": output,
#             "status": "completed",
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#         }
