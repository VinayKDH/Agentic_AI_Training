"""Enterprise multi-step agent service for Day3 Advanced."""

from __future__ import annotations

import logging
import operator
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.constants import (
    AGENT_SYSTEM_PROMPT,
    ENTERPRISE_POLICY_CHECKLIST,
)
from app.guardrails import scan_response, validate_query
from app.llm import active_model_label, get_llm
from app.resilience import with_retry

LOGGER = logging.getLogger("day3_enterprise")


class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], operator.add]
    query: str
    response: str
    run_id: str
    guardrail_status: Dict[str, Any]
    compliance: Dict[str, Any]
    policy_violations: Annotated[List[str], operator.add]
    audit_trail: Annotated[List[Dict[str, Any]], operator.add]
    blocked: bool


class AgentService:
    def __init__(self):
        self.llm = get_llm()
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        LOGGER.info("AgentService ready model=%s", active_model_label())

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("guardrails", self._guardrails_node)
        workflow.add_node("agent", self._agent_node)
        workflow.add_node("compliance_gate", self._compliance_node)
        workflow.set_entry_point("guardrails")
        workflow.add_conditional_edges(
            "guardrails",
            self._route_after_guardrails,
            {"agent": "agent", "end": END},
        )
        workflow.add_edge("agent", "compliance_gate")
        workflow.add_edge("compliance_gate", END)
        return workflow.compile(checkpointer=self.memory)

    def _route_after_guardrails(self, state: AgentState) -> str:
        return "end" if state.get("blocked") else "agent"

    def _guardrails_node(self, state: AgentState) -> dict:
        query = state.get("query") or ""
        if not query:
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    query = msg.content
                    break
        result = validate_query(query)
        audit = {
            "agent": "guardrails",
            "action": "validate_query",
            "ok": result.ok,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not result.ok:
            blocked_msg = (
                "Request blocked by enterprise input guardrails:\n- "
                + "\n- ".join(result.reasons)
            )
            return {
                "query": query,
                "blocked": True,
                "response": blocked_msg,
                "guardrail_status": {
                    "ok": False,
                    "reasons": result.reasons,
                    "findings": result.findings,
                },
                "policy_violations": result.reasons,
                "compliance": {"verdict": "blocked"},
                "messages": [AIMessage(content=blocked_msg)],
                "audit_trail": [audit],
            }
        return {
            "query": query,
            "blocked": False,
            "guardrail_status": {"ok": True, "reasons": [], "findings": result.findings},
            "audit_trail": [audit],
        }

    def _agent_node(self, state: AgentState) -> dict:
        query = state.get("query", "")
        checklist = "\n".join(f"- {item}" for item in ENTERPRISE_POLICY_CHECKLIST)
        messages = [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Enterprise policy checklist:\n{checklist}\n\n"
                    f"User request:\n{query}"
                )
            ),
        ]
        response = with_retry(lambda: self.llm.invoke(messages))
        content = response.content if hasattr(response, "content") else str(response)
        return {
            "response": content,
            "messages": [AIMessage(content=content)],
            "audit_trail": [
                {
                    "agent": "responder",
                    "action": "generate",
                    "model": active_model_label(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }

    def _compliance_node(self, state: AgentState) -> dict:
        response = state.get("response", "")
        scan = scan_response(response)
        verdict = "pass"
        violations: List[str] = []
        if not scan.ok:
            verdict = "fail"
            violations = scan.reasons
            response = (
                "Response withheld by enterprise output compliance gate:\n- "
                + "\n- ".join(scan.reasons)
            )
        return {
            "response": response,
            "compliance": {
                "verdict": verdict,
                "checklist": list(ENTERPRISE_POLICY_CHECKLIST),
                "findings": scan.findings,
            },
            "policy_violations": violations,
            "audit_trail": [
                {
                    "agent": "compliance",
                    "action": "scan_response",
                    "verdict": verdict,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "messages": [AIMessage(content=f"Compliance verdict: {verdict}")],
        }

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
            "guardrail_status": {},
            "compliance": {},
            "policy_violations": [],
            "audit_trail": [],
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
                    "guardrail_status": result.get("guardrail_status", {}),
                    "policy_violations": result.get("policy_violations", []),
                    "audit_trail": result.get("audit_trail", []),
                },
            }
        except Exception as exc:  # noqa: BLE001
            raise Exception(f"Agent execution failed: {exc}") from exc


agent_service = None


def get_agent_service():
    global agent_service
    if agent_service is None:
        agent_service = AgentService()
    return agent_service
