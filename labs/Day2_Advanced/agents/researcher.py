"""Researcher agent using LangChain create_agent + tools when available."""

from __future__ import annotations

from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from state import Task, TaskStatus
from tools.web_search import get_research_tools
from utils.constants import RESEARCH_TEMPERATURE, RESEARCHER_SYSTEM_PROMPT
from utils.llm import get_llm


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
                    "Optional search snippets:\n{search_results}\n\n"
                    "Provide concise findings with sources when possible.",
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
            # Fallback for environments without langchain.agents.create_agent
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
        """Run tool-using research for a task."""
        query = task["description"]
        if context:
            query = (
                f"{query}\n\nContext from previous work:\n"
                f"Research: {context.get('research', '')}\n"
                f"Code: {context.get('code', '')}"
            )

        try:
            if self.agent is not None:
                result = self.agent.invoke(
                    {"messages": [HumanMessage(content=query)]}
                )
                messages = result.get("messages", [])
                output = messages[-1].content if messages else str(result)
            else:
                search_results = self.tools[0].invoke(query[:240])
                response = (self.fallback_prompt | self.llm).invoke(
                    {"query": query, "search_results": search_results}
                )
                output = response.content

            return {
                "task_id": task["id"],
                "findings": output,
                "sources": self._extract_sources(str(output)),
                "status": TaskStatus.COMPLETED,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {
                "task_id": task["id"],
                "findings": f"Research error: {exc}",
                "sources": [],
                "status": TaskStatus.FAILED,
                "timestamp": datetime.now().isoformat(),
            }

    def _extract_sources(self, text: str) -> list:
        import re

        urls = re.findall(r"https?://[^\s)\]]+", text)
        return urls[:5]
