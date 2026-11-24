"""Enterprise LangGraph workflow for Customer Support Email Agent."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from nodes import (
    bug_tracking,
    classify_intent,
    doc_search,
    draft_response,
    human_review,
    read_email,
    route_after_classify,
    send_reply,
)
from state import EmailAgentState
from utils.constants import GRAPH_RECURSION_LIMIT


def create_email_agent_graph(enable_checkpoints: bool = True):
    workflow = StateGraph(EmailAgentState)

    workflow.add_node("read_email", read_email)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("doc_search", doc_search)
    workflow.add_node("bug_tracking", bug_tracking)
    workflow.add_node("draft_response", draft_response)
    workflow.add_node("human_review", human_review)
    workflow.add_node("send_reply", send_reply)

    workflow.add_edge(START, "read_email")
    workflow.add_edge("read_email", "classify_intent")
    workflow.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "doc_search": "doc_search",
            "bug_tracking": "bug_tracking",
            "human_review": "human_review",
            "draft_response": "draft_response",
            "send_reply": "send_reply",
        },
    )
    workflow.add_edge("doc_search", "draft_response")
    workflow.add_edge("bug_tracking", "draft_response")
    workflow.add_edge("draft_response", "human_review")
    workflow.add_edge("human_review", "send_reply")
    workflow.add_edge("send_reply", END)

    if enable_checkpoints:
        return workflow.compile(checkpointer=MemorySaver())
    return workflow.compile()


def default_run_config(thread_id: str) -> dict:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": GRAPH_RECURSION_LIMIT,
    }
