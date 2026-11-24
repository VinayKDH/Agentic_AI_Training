"""Enterprise researcher agent using LangChain create_agent + tools."""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from state import Task, TaskStatus
from tools.web_search import get_research_tools
from utils.constants import RESEARCH_TEMPERATURE, RESEARCHER_SYSTEM_PROMPT
from utils.guardrails import sanitize_for_prompt
from utils.llm import get_llm
from utils.resilience import with_retry


class ResearcherAgent:
    def __init__(self):
        self.llm = get_llm(temperature=RESEARCH_TEMPERATURE)
        self.tools = get_research_tools()
        self.agent = self._build_agent()
        self.fallback_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RESEARCHER_SYSTEM_PROMPT),
                (
                    "human",
                    "Research topic:\n{query}\n\n"
                    "Acceptance criteria:\n{acceptance}\n\n"
                    "Optional search snippets:\n{search_results}\n\n"
                    "Provide concise enterprise findings with sources when possible. "
                    "Separate facts vs assumptions and list risks.",
                ),
            ]
        )

    def _build_agent(self):
        try:
            from langchain.agents import create_agent

            return create_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=RESEARCHER_SYSTEM_PROMPT,
            )
        except Exception:
            try:
                from langgraph.prebuilt import create_react_agent

                return create_react_agent(
                    model=self.llm,
                    tools=self.tools,
                    prompt=RESEARCHER_SYSTEM_PROMPT,
                )
            except Exception:
                return None

    def research(self, task: Task, context: dict | None = None) -> dict:
        """Run tool-using research for a task with retries."""
        acceptance = "\n".join(
            f"- {item}" for item in (task.get("acceptance_criteria") or [])
        ) or "- Accurate, sourced, decision-ready findings"
        query = (
            f"{task['description']}\n\n"
            f"Acceptance criteria:\n{acceptance}\n"
            f"Risk level: {task.get('risk_level', 'medium')}\n"
            f"Priority: {task.get('priority', 'p1')}"
        )
        if context:
            query = (
                f"{query}\n\nContext from previous work:\n"
                f"Research: {sanitize_for_prompt(context.get('research', ''), 2000)}\n"
                f"Code: {sanitize_for_prompt(context.get('code', ''), 1500)}"
            )

        try:
            if self.agent is not None:
                result = with_retry(
                    lambda: self.agent.invoke(
                        {"messages": [HumanMessage(content=query)]}
                    ),
                    operation="researcher.agent",
                )
                messages = result.get("messages", [])
                output = messages[-1].content if messages else str(result)
            else:
                search_results = with_retry(
                    lambda: self.tools[0].invoke(query[:240]),
                    operation="researcher.search",
                )
                response = with_retry(
                    lambda: (self.fallback_prompt | self.llm).invoke(
                        {
                            "query": query,
                            "acceptance": acceptance,
                            "search_results": search_results,
                        }
                    ),
                    operation="researcher.fallback_llm",
                )
                output = response.content

            return {
                "task_id": task["id"],
                "findings": output,
                "sources": self._extract_sources(str(output)),
                "status": TaskStatus.COMPLETED,
                "risk_level": task.get("risk_level", "medium"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "task_id": task["id"],
                "findings": f"Research error: {exc}",
                "sources": [],
                "status": TaskStatus.FAILED,
                "risk_level": task.get("risk_level", "medium"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _extract_sources(self, text: str) -> list:
        import re

        urls = re.findall(r"https?://[^\s)\]]+", text)
        return urls[:8]
