#!/usr/bin/env python3
"""Interactive Day2 Advanced multi-agent demo with HITL resume support."""

from __future__ import annotations

import os
import uuid

from dotenv import load_dotenv

from graph.multi_agent_graph import MultiAgentGraph
from utils.constants import DEFAULT_THREAD_ID
from utils.llm import active_model_label

load_dotenv()

os.environ.setdefault("LLM_PROVIDER", "vertex")
os.environ.setdefault("GCP_PROJECT", "testkuberiq")
os.environ.setdefault("VERTEX_LOCATION", "us-central1")
os.environ.setdefault("VERTEX_MODEL", "gemini-2.5-flash")

broken_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if broken_adc and not os.path.exists(broken_adc):
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


def _print_stats(result: dict) -> None:
    tasks = result.get("tasks", [])
    completed = [
        task
        for task in tasks
        if getattr(task.get("status"), "value", task.get("status")) == "completed"
    ]
    print("\nStatistics:")
    print(f"- Tasks total: {len(tasks)}")
    print(f"- Tasks completed: {len(completed)}")
    print(f"- Research findings: {len(result.get('research_findings', []))}")
    print(f"- Code artifacts: {len(result.get('code_artifacts', []))}")
    print(f"- Reviews: {len(result.get('review_feedback', []))}")
    print("=" * 70)


def _handle_interrupt(graph: MultiAgentGraph, config: dict, result) -> dict:
    """Pause for human input when LangGraph interrupt() is triggered."""
    while True:
        interrupts = []
        if isinstance(result, dict):
            interrupts = result.get("__interrupt__", [])
        if not interrupts:
            state = graph.get_state(config)
            if state and state.next:
                # Interrupted but payload already consumed from invoke return
                print("\n[HITL] Graph paused for human input.")
                decision = input(
                    "Enter decision (approve/revise/guidance), or 'exit': "
                ).strip()
                if decision.lower() in {"exit", "quit"}:
                    return result if isinstance(result, dict) else {"final_output": ""}
                result = graph.resume(decision, config)
                continue
            break

        payload = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
        print("\n" + "=" * 70)
        print("HUMAN-IN-THE-LOOP REVIEW GATE")
        print("=" * 70)
        if isinstance(payload, dict):
            print(f"Task: {payload.get('task')}")
            print(f"Score: {payload.get('score')}")
            print(f"Feedback:\n{payload.get('feedback')}")
            print(f"\n{payload.get('prompt')}")
        else:
            print(payload)

        decision = input("\nYour decision: ").strip()
        if decision.lower() in {"exit", "quit"}:
            return result if isinstance(result, dict) else {"final_output": ""}
        result = graph.resume(decision, config)
    return result if isinstance(result, dict) else {"final_output": str(result)}


def main() -> None:
    print("=" * 70)
    print("Day 2 Advanced — Modern Multi-Agent System")
    print("=" * 70)
    print("\nCapabilities:")
    print("- LangGraph StateGraph + MemorySaver checkpoints")
    print("- Command-based routing")
    print("- Tool-calling researcher (create_agent)")
    print("- Structured planner/coder/reviewer outputs")
    print("- Human-in-the-loop interrupt() on review rejection")
    print(f"\nLLM: {active_model_label()}")
    print("\n" + "=" * 70)

    enable_hitl = os.getenv("ENABLE_HITL", "true").lower() in {"1", "true", "yes"}
    graph = MultiAgentGraph(
        enable_checkpoints=True,
        enable_human_review=enable_hitl,
    )

    while True:
        query = input("\nEnter your query (or 'exit' to quit): ").strip()
        if query.lower() in {"exit", "quit"}:
            break
        if not query:
            continue

        thread_id = f"{DEFAULT_THREAD_ID}-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}
        print(f"\nProcessing: {query}")
        print(f"Thread: {thread_id}")
        print("-" * 70)

        try:
            result = graph.run(query, config)
            result = _handle_interrupt(graph, config, result)

            print("\n" + "=" * 70)
            print("FINAL OUTPUT")
            print("=" * 70)
            print(result.get("final_output") or "(empty — maybe interrupted)")
            print("\n" + "=" * 70)
            _print_stats(result)
        except Exception as exc:
            print(f"\nError: {exc}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
