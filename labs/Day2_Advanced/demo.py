#!/usr/bin/env python3
"""Non-interactive Day2 Advanced demo runner."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Prefer Vertex for demo; ignore broken ADC path if present.
os.environ.setdefault("LLM_PROVIDER", "vertex")
os.environ.setdefault("GCP_PROJECT", "testkuberiq")
os.environ.setdefault("VERTEX_LOCATION", "us-central1")
os.environ.setdefault("VERTEX_MODEL", "gemini-2.5-flash")
broken_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if broken_adc and not os.path.exists(broken_adc):
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

from graph.multi_agent_graph import MultiAgentGraph
from utils.constants import DEMO_QUERY


def main():
    query = " ".join(sys.argv[1:]).strip() or DEMO_QUERY

    print("=" * 70)
    print("Day 2 Advanced — Multi-Agent Demo")
    print("=" * 70)
    print("Agents: Planner → Researcher → Coder → Reviewer → Synthesizer")
    print(f"LLM: {os.getenv('LLM_PROVIDER')} / {os.getenv('VERTEX_MODEL')}")
    print(f"\nQuery: {query}")
    print("-" * 70)

    graph = MultiAgentGraph(enable_checkpoints=True)
    result = graph.run(query, {"configurable": {"thread_id": "demo_thread"}})

    print("\n" + "=" * 70)
    print("FINAL OUTPUT")
    print("=" * 70)
    print(result.get("final_output") or "(empty)")
    print("\n" + "=" * 70)
    print("Statistics:")
    tasks = result.get("tasks", [])
    completed = [t for t in tasks if getattr(t.get("status"), "value", t.get("status")) == "completed"]
    print(f"- Tasks total: {len(tasks)}")
    print(f"- Tasks completed: {len(completed)}")
    print(f"- Research findings: {len(result.get('research_findings', []))}")
    print(f"- Code artifacts: {len(result.get('code_artifacts', []))}")
    print(f"- Reviews: {len(result.get('review_feedback', []))}")
    print("=" * 70)


if __name__ == "__main__":
    main()
