"""Research tools for tool-calling agents."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information about a topic.

    Args:
        query: Search query string.
    """
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "No search results found."
        lines = []
        for item in results:
            title = item.get("title", "")
            href = item.get("href", "")
            body = item.get("body", "")
            lines.append(f"- {title}\n  URL: {href}\n  Snippet: {body}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Search unavailable ({exc}). Use your existing knowledge."


def get_research_tools() -> list:
    return [web_search]
