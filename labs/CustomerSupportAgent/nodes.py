"""Enterprise node implementations for Customer Support Email Agent."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from state import EmailAgentState
from utils.constants import (
    CLASSIFIER_SYSTEM_PROMPT,
    CLASSIFY_TEMPERATURE,
    DRAFT_SYSTEM_PROMPT,
    DRAFT_TEMPERATURE,
    KNOWLEDGE_BASE,
    SUPPORT_POLICY_CHECKLIST,
)
from utils.guardrails import redact_secrets, validate_inbound_email
from utils.llm import active_model_label, get_llm
from utils.policies import evaluate_draft, requires_human_review, sla_hours_for_urgency
from utils.resilience import with_retry


class EmailClassificationModel(BaseModel):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str
    sentiment: Literal["negative", "neutral", "positive"] = "neutral"


def _audit(agent: str, action: str, **details):
    return {
        "agent": agent,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": active_model_label(),
        **details,
    }


def read_email(state: EmailAgentState) -> dict:
    print("\n[Read Email] Processing inbound email...")
    email_content = state.get("email_content", "")
    sender_email = state.get("sender_email", "")
    email_id = state.get("email_id", "")

    guard = validate_inbound_email(email_content, sender_email)
    if not guard.ok:
        print(f"[Read Email] Guardrail block: {guard.reasons}")
        return {
            "errors": guard.reasons,
            "policy_violations": guard.reasons,
            "guardrail_status": {
                "ok": False,
                "reasons": guard.reasons,
                "findings": guard.findings,
            },
            "final_response": (
                "Email could not be processed due to inbound validation failures:\n- "
                + "\n- ".join(guard.reasons)
            ),
            "compliance": {"verdict": "blocked"},
            "audit_trail": [_audit("read_email", "blocked", reasons=guard.reasons)],
        }

    safe_content = redact_secrets(email_content)
    print(f"[Read Email] From: {sender_email} | ID: {email_id}")
    return {
        "email_content": safe_content,
        "guardrail_status": {
            "ok": True,
            "reasons": guard.reasons,
            "findings": guard.findings,
        },
        "messages": [
            HumanMessage(content=f"Email from {sender_email}: {safe_content}")
        ],
        "audit_trail": [_audit("read_email", "accepted", findings=len(guard.findings))],
    }


def classify_intent(state: EmailAgentState) -> dict:
    print("\n[Classify Intent] Analyzing email...")
    if state.get("compliance", {}).get("verdict") == "blocked":
        return {}

    email_content = state.get("email_content", "")
    sender_email = state.get("sender_email", "")
    llm = get_llm(temperature=CLASSIFY_TEMPERATURE).with_structured_output(
        EmailClassificationModel
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CLASSIFIER_SYSTEM_PROMPT),
            (
                "human",
                "From: {sender_email}\n\nContent:\n{email_content}\n\n"
                "Classify intent, urgency, topic, summary, and sentiment.",
            ),
        ]
    )

    t0 = time.perf_counter()
    try:
        result: EmailClassificationModel = with_retry(
            lambda: (prompt | llm).invoke(
                {"sender_email": sender_email, "email_content": email_content}
            )
        )
        classification = result.model_dump()
        classification["sla_hours"] = sla_hours_for_urgency(classification["urgency"])
        print(
            f"[Classify Intent] {classification['intent']} / "
            f"{classification['urgency']} / SLA {classification['sla_hours']}h"
        )
        return {
            "classification": classification,
            "messages": [
                AIMessage(
                    content=(
                        f"Classification: {classification['intent']} "
                        f"({classification['urgency']}) — {classification['summary']}"
                    )
                )
            ],
            "audit_trail": [
                _audit(
                    "classify",
                    "classified",
                    intent=classification["intent"],
                    urgency=classification["urgency"],
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                )
            ],
        }
    except Exception as exc:  # noqa: BLE001
        error_msg = f"Classification error: {exc}"
        print(f"[Classify Intent] {error_msg}")
        fallback = {
            "intent": "complex",
            "urgency": "high",
            "topic": "classification_failure",
            "summary": error_msg,
            "sentiment": "neutral",
            "sla_hours": sla_hours_for_urgency("high"),
        }
        return {
            "errors": [error_msg],
            "classification": fallback,
            "audit_trail": [_audit("classify", "fallback", error=str(exc))],
        }


def route_after_classify(state: EmailAgentState) -> str:
    if state.get("compliance", {}).get("verdict") == "blocked":
        return "send_reply"
    classification = state.get("classification") or {}
    intent = classification.get("intent", "")
    urgency = classification.get("urgency", "medium")
    if intent == "bug":
        return "bug_tracking"
    if urgency == "critical" or intent == "complex":
        return "human_review"
    if intent == "question":
        return "doc_search"
    return "draft_response"


def doc_search(state: EmailAgentState) -> dict:
    print("\n[Doc Search] Searching enterprise knowledge base...")
    classification = state.get("classification") or {}
    topic = classification.get("topic", "")
    email_content = state.get("email_content", "")
    search_query = f"{topic} {email_content}".lower()

    results = []
    for key, value in KNOWLEDGE_BASE.items():
        if key.lower() in search_query or any(
            token in search_query for token in key.lower().split()
        ):
            results.append(value)

    if not results:
        try:
            from langchain_community.tools import DuckDuckGoSearchRun

            web_result = with_retry(
                lambda: DuckDuckGoSearchRun().run(
                    f"{topic} {classification.get('summary', '')}"
                )
            )
            results.append(str(web_result)[:500])
        except Exception as exc:  # noqa: BLE001
            print(f"[Doc Search] Web search unavailable: {exc}")

    print(f"[Doc Search] Found {len(results)} result(s)")
    return {
        "search_results": results,
        "messages": [
            AIMessage(content=f"Found {len(results)} documentation result(s)")
        ],
        "audit_trail": [_audit("doc_search", "searched", result_count=len(results))],
    }


def bug_tracking(state: EmailAgentState) -> dict:
    print("\n[Bug Tracking] Opening enterprise ticket...")
    classification = state.get("classification") or {}
    email_content = state.get("email_content", "")
    sender_email = state.get("sender_email", "")
    ticket_id = (
        f"BUG-{datetime.now(timezone.utc).strftime('%Y%m%d')}-"
        f"{abs(hash(email_content)) % 10000:04d}"
    )
    bug_info = {
        "ticket_id": ticket_id,
        "reporter": sender_email,
        "description": email_content,
        "topic": classification.get("topic", ""),
        "urgency": classification.get("urgency", "medium"),
        "sla_hours": classification.get("sla_hours"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    print(f"[Bug Tracking] Created {ticket_id}")
    print(json.dumps(bug_info, indent=2))
    return {
        "bug_ticket_id": ticket_id,
        "messages": [AIMessage(content=f"Bug ticket created: {ticket_id}")],
        "audit_trail": [_audit("bug_tracking", "created", ticket_id=ticket_id)],
    }


def draft_response(state: EmailAgentState) -> dict:
    print("\n[Draft Response] Generating enterprise reply...")
    classification = state.get("classification") or {}
    email_content = state.get("email_content", "")
    search_results = state.get("search_results") or []
    bug_ticket_id = state.get("bug_ticket_id")
    customer_history = state.get("customer_history") or {}
    checklist = "\n".join(f"- {item}" for item in SUPPORT_POLICY_CHECKLIST)

    context_parts = []
    if search_results:
        context_parts.append("Documentation:\n" + "\n".join(search_results))
    if bug_ticket_id:
        context_parts.append(
            f"Bug ticket created: {bug_ticket_id}. Reference it for follow-up."
        )
    if customer_history:
        context_parts.append(f"Customer history: {json.dumps(customer_history)}")
    context = "\n\n".join(context_parts) or "No additional context."

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DRAFT_SYSTEM_PROMPT),
            (
                "human",
                "Policy checklist:\n{checklist}\n\n"
                "Original email:\n{email_content}\n\n"
                "Intent: {intent}\nUrgency: {urgency}\nTopic: {topic}\n"
                "Summary: {summary}\nSLA hours: {sla_hours}\n\n"
                "Context:\n{context}\n\nDraft the customer email reply.",
            ),
        ]
    )

    try:
        response = with_retry(
            lambda: (prompt | get_llm(temperature=DRAFT_TEMPERATURE)).invoke(
                {
                    "checklist": checklist,
                    "email_content": email_content,
                    "intent": classification.get("intent", "question"),
                    "urgency": classification.get("urgency", "medium"),
                    "topic": classification.get("topic", ""),
                    "summary": classification.get("summary", ""),
                    "sla_hours": classification.get("sla_hours", 24),
                    "context": context,
                }
            )
        )
        draft = response.content if hasattr(response, "content") else str(response)
        draft = redact_secrets(draft)
        policy = evaluate_draft(draft, classification)
        update = {
            "draft_response": draft,
            "messages": [AIMessage(content="Draft response generated")],
            "audit_trail": [
                _audit(
                    "draft",
                    "generated",
                    chars=len(draft),
                    policy_passed=policy["passed"],
                )
            ],
        }
        if policy["violations"]:
            update["policy_violations"] = policy["violations"]
        return update
    except Exception as exc:  # noqa: BLE001
        error_msg = f"Response drafting error: {exc}"
        print(f"[Draft Response] {error_msg}")
        return {
            "errors": [error_msg],
            "draft_response": (
                "Thank you for contacting support. We received your request and a "
                "specialist will follow up shortly."
            ),
            "audit_trail": [_audit("draft", "fallback", error=str(exc))],
        }


def human_review(state: EmailAgentState) -> dict:
    print("\n[Human Review] Evaluating escalation policy...")
    if state.get("compliance", {}).get("verdict") == "blocked":
        return {"requires_human_review": False, "human_approved": False}

    classification = state.get("classification")
    draft = state.get("draft_response")
    needs_review = requires_human_review(classification, draft)
    enable_hitl = bool(state.get("enable_hitl"))

    if needs_review and enable_hitl:
        print("[Human Review] Pausing for human decision...")
        decision = interrupt(
            {
                "type": "support_review_gate",
                "email_id": state.get("email_id"),
                "sender_email": state.get("sender_email"),
                "classification": classification,
                "draft_response": draft,
                "policy_violations": state.get("policy_violations") or [],
                "prompt": (
                    "Reply with 'approve', edited response text, or 'escalate'."
                ),
            }
        )
        text = str(decision).strip()
        lowered = text.lower()
        if lowered in {"approve", "approved", "yes", "y"}:
            return {
                "requires_human_review": True,
                "human_approved": True,
                "human_edited_response": draft,
                "audit_trail": [_audit("human_review", "approved")],
            }
        if lowered in {"escalate", "reject", "no"}:
            return {
                "requires_human_review": True,
                "human_approved": False,
                "human_edited_response": (
                    "Your request has been escalated to a specialist. "
                    "We will follow up within the stated SLA."
                ),
                "audit_trail": [_audit("human_review", "escalated")],
            }
        return {
            "requires_human_review": True,
            "human_approved": True,
            "human_edited_response": text,
            "audit_trail": [_audit("human_review", "edited")],
        }

    if needs_review:
        print("[Human Review] Required (auto-approved for non-interactive run)")
        return {
            "requires_human_review": True,
            "human_approved": True,
            "human_edited_response": draft,
            "audit_trail": [_audit("human_review", "auto_approved")],
        }

    print("[Human Review] Auto-approved by policy")
    return {
        "requires_human_review": False,
        "human_approved": True,
        "audit_trail": [_audit("human_review", "skipped")],
    }


def send_reply(state: EmailAgentState) -> dict:
    print("\n[Send Reply] Finalizing outbound response...")
    if state.get("final_response") and state.get("compliance", {}).get("verdict") == "blocked":
        return {
            "audit_trail": [_audit("send_reply", "skipped_blocked")],
        }

    if state.get("human_edited_response"):
        final_response = state["human_edited_response"]
    elif state.get("draft_response"):
        final_response = state["draft_response"]
    else:
        final_response = (
            "Thank you for contacting us. We received your email and will respond shortly."
        )

    final_response = redact_secrets(final_response or "")
    policy = evaluate_draft(final_response, state.get("classification"))
    verdict = "pass" if policy["passed"] else "fail"
    if not policy["passed"]:
        final_response = (
            "Thank you for contacting support. A specialist will follow up shortly "
            "because the automated draft did not pass compliance checks."
        )
        verdict = "conditional"

    sender = state.get("sender_email", "")
    print(f"[Send Reply] To: {sender}")
    print(f"[Send Reply] Preview: {final_response[:120]}...")
    return {
        "final_response": final_response,
        "compliance": {
            "verdict": verdict,
            "checklist": list(SUPPORT_POLICY_CHECKLIST),
            "violations": policy["violations"],
            "warnings": policy["warnings"],
        },
        "policy_violations": policy["violations"],
        "messages": [AIMessage(content=f"Response prepared for {sender}")],
        "audit_trail": [_audit("send_reply", "finalized", verdict=verdict)],
    }
