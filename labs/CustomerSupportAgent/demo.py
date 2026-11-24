#!/usr/bin/env python3
"""Non-interactive enterprise demo for Customer Support Email Agent."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path="../.env.azure", override=False)
os.environ.setdefault("LLM_PROVIDER", "azure")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

from graph import create_email_agent_graph, default_run_config
from utils.llm import active_model_label


DEMO_EMAIL = {
    "email_id": "demo_001",
    "sender_email": "customer@example.com",
    "email_content": (
        "How do I reset my password? I can't sign in and need access today."
    ),
}


def main() -> None:
    email = DEMO_EMAIL.copy()
    if len(sys.argv) > 1:
        email["email_content"] = " ".join(sys.argv[1:]).strip()

    print("=" * 70)
    print("Customer Support Agent — Enterprise Demo")
    print("=" * 70)
    print(f"LLM: {active_model_label()}")
    print(f"From: {email['sender_email']}")
    print(f"Content: {email['email_content']}")
    print("-" * 70)

    graph = create_email_agent_graph(enable_checkpoints=True)
    initial_state = {
        "email_content": email["email_content"],
        "sender_email": email["sender_email"],
        "email_id": email["email_id"],
        "classification": None,
        "search_results": None,
        "customer_history": None,
        "bug_ticket_id": None,
        "draft_response": None,
        "final_response": None,
        "messages": [],
        "requires_human_review": False,
        "human_approved": None,
        "human_edited_response": None,
        "enable_hitl": False,
        "errors": [],
        "policy_violations": [],
        "guardrail_status": {},
        "compliance": {},
        "run_id": email["email_id"],
        "run_metadata": {},
        "metrics": {},
        "audit_trail": [],
    }
    result = graph.invoke(initial_state, default_run_config(email["email_id"]))

    classification = result.get("classification") or {}
    print("\nClassification:")
    print(f"  Intent: {classification.get('intent')}")
    print(f"  Urgency: {classification.get('urgency')}")
    print(f"  SLA hours: {classification.get('sla_hours')}")
    print(f"  Topic: {classification.get('topic')}")
    if result.get("bug_ticket_id"):
        print(f"\nBug ticket: {result['bug_ticket_id']}")
    print("\nFinal response:")
    print("-" * 70)
    print(result.get("final_response") or "(empty)")
    print("-" * 70)
    print(f"Compliance: {(result.get('compliance') or {}).get('verdict', 'n/a')}")
    print(f"Audit events: {len(result.get('audit_trail') or [])}")
    print("=" * 70)


if __name__ == "__main__":
    main()
