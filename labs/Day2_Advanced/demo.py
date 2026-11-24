#!/usr/bin/env python3
"""Non-interactive Day2 Advanced enterprise demo (HITL disabled)."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path="../.env.azure", override=False)

os.environ.setdefault("LLM_PROVIDER", "azure")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

broken_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if broken_adc and not os.path.exists(broken_adc):
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

from graph.multi_agent_graph import MultiAgentGraph
from utils.constants import DEMO_QUERY, DEFAULT_THREAD_ID
from utils.llm import active_model_label


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or DEMO_QUERY
    print("=" * 70)
    print("Day 2 Advanced — Enterprise Multi-Agent Demo")
    print("=" * 70)
    print("Flow: Planner → Dispatch → Researcher/Coder → Reviewer → Synthesizer")
    print("Gates: input guardrails · policy checks · quality scoring · audit trail")
    print(f"LLM: {active_model_label()}")
    print(f"\nQuery: {query}")
    print("-" * 70)

    graph = MultiAgentGraph(enable_checkpoints=True, enable_human_review=False)
    config = {"configurable": {"thread_id": f"{DEFAULT_THREAD_ID}-oneshot"}}

    for update in graph.stream(query, config):
        node_name = next(iter(update.keys()))
        print(f"\n>> Node update: {node_name}")

    result = graph.get_state(config).values
    print("\n" + "=" * 70)
    print("FINAL OUTPUT")
    print("=" * 70)
    print(result.get("final_output") or "(empty)")
    print("\n" + "=" * 70)
    print(MultiAgentGraph.format_report(result))
    print("=" * 70)
    tasks = result.get("tasks", [])
    completed = [
        task
        for task in tasks
        if getattr(task.get("status"), "value", task.get("status")) == "completed"
    ]
    print("Statistics:")
    print(f"- Tasks total: {len(tasks)}")
    print(f"- Tasks completed: {len(completed)}")
    print(f"- Research findings: {len(result.get('research_findings', []))}")
    print(f"- Code artifacts: {len(result.get('code_artifacts', []))}")
    print(f"- Reviews: {len(result.get('review_feedback', []))}")
    print(f"- Compliance: {(result.get('compliance') or {}).get('verdict', 'n/a')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
