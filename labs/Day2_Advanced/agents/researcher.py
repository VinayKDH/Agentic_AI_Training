from langchain_core.prompts import ChatPromptTemplate
from state import Task, TaskStatus
from utils.llm import get_llm
from datetime import datetime


class ResearcherAgent:
    def __init__(self):
        self.llm = get_llm(temperature=0.5)
        self.search_tool = None
        try:
            from langchain_community.tools import DuckDuckGoSearchRun

            self.search_tool = DuckDuckGoSearchRun()
        except Exception:
            self.search_tool = None

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a research assistant. Produce concise, accurate findings.
            Prefer practical bullet points. If search snippets are provided, ground your answer in them."""),
            ("human", """Research topic: {query}

Search snippets:
{search_results}

Provide detailed findings focused on accuracy and relevance."""),
        ])

    def research(self, task: Task, context: dict = None) -> dict:
        """Perform research for a task."""
        query = task["description"]
        if context:
            query = f"{query}\n\nContext from previous tasks: {context}"

        search_results = "No live search available; use your knowledge."
        if self.search_tool:
            try:
                search_results = self.search_tool.run(query[:240])
            except Exception as e:
                search_results = f"Search unavailable ({e}). Use your knowledge."

        try:
            response = (self.prompt | self.llm).invoke({
                "query": query,
                "search_results": search_results,
            })
            output = response.content
            return {
                "task_id": task["id"],
                "findings": output,
                "sources": self._extract_sources(f"{output}\n{search_results}"),
                "status": TaskStatus.COMPLETED,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "task_id": task["id"],
                "findings": f"Research error: {str(e)}",
                "sources": [],
                "status": TaskStatus.FAILED,
                "timestamp": datetime.now().isoformat(),
            }

    def _extract_sources(self, text: str) -> list:
        import re

        urls = re.findall(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            text,
        )
        return urls[:5]
