#!/usr/bin/env python3
"""Interactive enterprise Customer Support Email Agent."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv()
load_dotenv(dotenv_path="../.env.azure", override=False)
os.environ.setdefault("LLM_PROVIDER", "azure")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

from graph import create_email_agent_graph, default_run_config
from utils.llm import active_model_label


EXAMPLE_EMAILS = [
    {
        "email_id": "email_001",
        "sender_email": "customer@example.com",
        "email_content": "How do I reset my password? I can't remember it.",
    },
    {
        "email_id": "email_002",
        "sender_email": "user@example.com",
        "email_content": (
            "The export feature crashes when I select PDF format. This is very frustrating!"
        ),
    },
    {
        "email_id": "email_003",
        "sender_email": "billing@company.com",
        "email_content": (
            "I was charged twice for my subscription! This is urgent! Please fix this immediately."
        ),
    },
    {
        "email_id": "email_004",
        "sender_email": "developer@startup.com",
        "email_content": "Can you add dark mode to the mobile app? It would be really helpful.",
    },
    {
        "email_id": "email_005",
        "sender_email": "tech@enterprise.com",
        "email_content": (
            "Our API integration fails intermittently with 504 errors. We've tried everything "
            "but can't figure out the root cause. This is affecting our production system."
        ),
    },
]


def _initial_state(email_data: dict, enable_hitl: bool) -> dict:
    return {
        "email_content": email_data["email_content"],
        "sender_email": email_data["sender_email"],
        "email_id": email_data["email_id"],
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
        "enable_hitl": enable_hitl,
        "errors": [],
        "policy_violations": [],
        "guardrail_status": {},
        "compliance": {},
        "run_id": email_data["email_id"],
        "run_metadata": {},
        "metrics": {},
        "audit_trail": [],
    }


def _print_result(result: dict) -> None:
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    classification = result.get("classification")
    if classification:
        print("\nClassification:")
        print(f"  Intent: {classification.get('intent')}")
        print(f"  Urgency: {classification.get('urgency')}")
        print(f"  Sentiment: {classification.get('sentiment')}")
        print(f"  SLA hours: {classification.get('sla_hours')}")
        print(f"  Topic: {classification.get('topic')}")
        print(f"  Summary: {classification.get('summary')}")
    if result.get("bug_ticket_id"):
        print(f"\nBug Ticket: {result['bug_ticket_id']}")
    if result.get("search_results"):
        print(f"\nDocumentation Results: {len(result['search_results'])} found")
    if result.get("final_response"):
        print("\nFinal Response:")
        print("-" * 70)
        print(result["final_response"])
        print("-" * 70)
    compliance = result.get("compliance") or {}
    print(f"\nCompliance: {compliance.get('verdict', 'n/a')}")
    if result.get("policy_violations"):
        print("Policy violations:")
        for item in result["policy_violations"]:
            print(f"  - {item}")
    if result.get("errors"):
        print(f"\nErrors: {len(result['errors'])}")
        for error in result["errors"]:
            print(f"  - {error}")
    print("=" * 70)


def _extract_interrupts(snapshot) -> list:
    if snapshot is None:
        return []
    values = []
    for task in getattr(snapshot, "tasks", None) or ():
        for item in getattr(task, "interrupts", None) or ():
            values.append(getattr(item, "value", item))
    if values:
        return values
    return [
        getattr(item, "value", item)
        for item in (getattr(snapshot, "interrupts", None) or ())
    ]


def process_email(graph, email_data: dict, enable_hitl: bool = False) -> None:
    print("\n" + "=" * 70)
    print("PROCESSING EMAIL")
    print("=" * 70)
    print(f"Email ID: {email_data['email_id']}")
    print(f"From: {email_data['sender_email']}")
    print(f"Content: {email_data['email_content'][:120]}...")
    print("=" * 70)

    config = default_run_config(email_data["email_id"])
    try:
        result = graph.invoke(_initial_state(email_data, enable_hitl), config)
        while True:
            snapshot = graph.get_state(config)
            interrupts = _extract_interrupts(snapshot)
            if not interrupts:
                if isinstance(result, dict) and result.get("__interrupt__"):
                    interrupts = [
                        getattr(item, "value", item)
                        for item in result["__interrupt__"]
                    ]
                else:
                    break
            payload = interrupts[0]
            print("\n" + "=" * 70)
            print("HUMAN REVIEW GATE")
            print("=" * 70)
            if isinstance(payload, dict):
                print(f"Draft:\n{payload.get('draft_response')}")
                print(f"\n{payload.get('prompt')}")
            else:
                print(payload)
            decision = input("\nYour decision: ").strip()
            if decision.lower() in {"exit", "quit"}:
                return
            result = graph.invoke(Command(resume=decision), config)

        values = graph.get_state(config).values if graph.get_state(config) else result
        _print_result(values if isinstance(values, dict) else result)
    except Exception as exc:  # noqa: BLE001
        print(f"\nError processing email: {exc}")
        import traceback

        traceback.print_exc()


def main() -> None:
    print("=" * 70)
    print("Customer Support Email Agent — Enterprise")
    print("=" * 70)
    print(f"LLM: {active_model_label()}")
    print(
        "Flow: read → classify → doc/bug → draft → human review → send"
    )
    print("Gates: inbound validation · secret redaction · SLA · compliance")
    print("=" * 70)

    enable_hitl = os.getenv("ENABLE_HITL", "false").lower() in {"1", "true", "yes"}
    graph = create_email_agent_graph(enable_checkpoints=True)

    while True:
        print("\nOptions:")
        print("1. Process example emails")
        print("2. Enter custom email")
        print("3. Exit")
        choice = input("\nEnter your choice (1-3): ").strip()
        if choice == "1":
            for i, email in enumerate(EXAMPLE_EMAILS, 1):
                print(f"{i}. {email['email_content'][:70]}...")
            email_choice = input("\nSelect email number (1-5): ").strip()
            try:
                email_idx = int(email_choice) - 1
                if 0 <= email_idx < len(EXAMPLE_EMAILS):
                    process_email(graph, EXAMPLE_EMAILS[email_idx], enable_hitl)
                else:
                    print("Invalid email number!")
            except ValueError:
                print("Invalid input!")
        elif choice == "2":
            email_id = input("Email ID: ").strip() or "custom_email_001"
            sender_email = input("Sender email: ").strip() or "customer@example.com"
            print("Email content (press Enter twice when done):")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            email_content = "\n".join(lines).strip()
            if email_content:
                process_email(
                    graph,
                    {
                        "email_id": email_id,
                        "sender_email": sender_email,
                        "email_content": email_content,
                    },
                    enable_hitl,
                )
            else:
                print("No email content provided!")
        elif choice == "3":
            print("\nGoodbye!")
            break
        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main()
