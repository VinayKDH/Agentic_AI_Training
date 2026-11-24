"""Enterprise state schema for Customer Support Email Agent."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

import operator
from langchain_core.messages import BaseMessage


class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str
    sentiment: str
    sla_hours: int


class EmailAgentState(TypedDict, total=False):
    email_content: str
    sender_email: str
    email_id: str

    classification: Optional[EmailClassification]
    search_results: Optional[List[str]]
    customer_history: Optional[Dict[str, Any]]
    bug_ticket_id: Optional[str]

    draft_response: Optional[str]
    final_response: Optional[str]

    messages: Annotated[List[BaseMessage], operator.add]

    requires_human_review: bool
    human_approved: Optional[bool]
    human_edited_response: Optional[str]
    enable_hitl: bool

    errors: Annotated[List[str], operator.add]
    policy_violations: Annotated[List[str], operator.add]
    guardrail_status: Dict[str, Any]
    compliance: Dict[str, Any]
    run_id: str
    run_metadata: Dict[str, Any]
    metrics: Dict[str, Any]
    audit_trail: Annotated[List[Dict[str, Any]], operator.add]
