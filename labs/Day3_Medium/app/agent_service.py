"""Enterprise-hardened agent service for Day3 Medium."""

from __future__ import annotations

import operator
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncIterator, Dict, List, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.constants import (
    AGENT_SYSTEM_PROMPT,
    LLM_MAX_RETRIES,
    MAX_QUERY_LENGTH,
    PROMPT_INJECTION_MARKERS,
    SECRET_PATTERNS,
)
from app.llm import active_model_label, get_llm

load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env.azure"), override=False)
os.environ.setdefault("LLM_PROVIDER", "azure")


class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], operator.add]
    query: str
    response: str
    run_id: str
    compliance: Dict[str, Any]
    blocked: bool


def _validate_query(query: str) -> list[str]:
    reasons = []
    text = (query or "").strip()
    if not text:
        reasons.append("Empty query")
    if len(text) > MAX_QUERY_LENGTH:
        reasons.append("Query too long")
    lowered = text.lower()
    if any(marker in lowered for marker in PROMPT_INJECTION_MARKERS):
        reasons.append("Prompt-injection language detected")
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text):
            reasons.append("Possible secret in query")
            break
    return reasons


class AgentService:
    def __init__(self):
        self.llm = get_llm()
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent_node)
        workflow.set_entry_point("agent")
        workflow.add_edge("agent", END)
        return workflow.compile(checkpointer=self.memory)

    def _agent_node(self, state: AgentState) -> dict:
        query = state.get("query", "")
        reasons = _validate_query(query)
        if reasons:
            msg = "Blocked by enterprise guardrails:\n- " + "\n- ".join(reasons)
            return {
                "blocked": True,
                "response": msg,
                "compliance": {"verdict": "blocked"},
                "messages": [AIMessage(content=msg)],
            }

        messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]
        last_error = None
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                response = self.llm.invoke(messages)
                content = response.content if hasattr(response, "content") else str(response)
                return {
                    "blocked": False,
                    "response": content,
                    "compliance": {"verdict": "pass"},
                    "messages": [AIMessage(content=content)],
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.5 * attempt)
        raise RuntimeError(f"LLM failed after retries: {last_error}")

    async def process_query(
        self,
        query: str,
        session_id: str = None,
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        start_time = time.time()
        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message_count": 0,
            }

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        config = {"configurable": {"thread_id": session_id}}
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "response": "",
            "run_id": run_id,
            "compliance": {},
            "blocked": False,
        }
        try:
            result = self.graph.invoke(initial_state, config)
            execution_time = time.time() - start_time
            self.sessions[session_id]["message_count"] += 1
            self.sessions[session_id]["last_activity"] = datetime.now(
                timezone.utc
            ).isoformat()
            return {
                "response": result.get("response", ""),
                "session_id": session_id,
                "execution_time": execution_time,
                "metadata": {
                    "run_id": run_id,
                    "model": active_model_label(),
                    "message_count": self.sessions[session_id]["message_count"],
                    "iterations": 1,
                    "compliance": result.get("compliance", {}),
                },
            }
        except Exception as exc:  # noqa: BLE001
            raise Exception(f"Agent execution failed: {exc}") from exc

    async def stream_query(
        self,
        query: str,
        session_id: str = None,
    ) -> AsyncIterator[str]:
        result = await self.process_query(query, session_id=session_id)
        response = result.get("response", "")
        words = response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            import asyncio

            await asyncio.sleep(0.03)

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        return self.sessions[session_id]

    def clear_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


agent_service = None


def get_agent_service():
    global agent_service
    if agent_service is None:
        agent_service = AgentService()
    return agent_service
