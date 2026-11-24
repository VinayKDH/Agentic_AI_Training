"""Application service wrapping MultiAgentGraph for the web console."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional

from langgraph.types import Command

from graph.multi_agent_graph import MultiAgentGraph
from ui.serializers import summarize_state, to_jsonable
from utils.constants import DEFAULT_THREAD_ID, GRAPH_RECURSION_LIMIT
from utils.llm import active_model_label
from utils.observability import format_run_report


@dataclass
class ActiveRun:
    thread_id: str
    graph: MultiAgentGraph
    enable_hitl: bool
    query: str
    autonomy_level: str = "L2"
    lock: threading.Lock = field(default_factory=threading.Lock)


class AgentConsoleService:
    """Keeps in-memory run sessions so HITL resume works from the UI."""

    def __init__(self) -> None:
        self._runs: Dict[str, ActiveRun] = {}
        self._lock = threading.Lock()

    def config(self) -> dict:
        from utils.governance import AutonomyGovernor

        return {
            "model": active_model_label(),
            "provider": active_model_label().split("/", 1)[0],
            "hitl_default": False,
            "governance": AutonomyGovernor().catalog(),
        }

    def _register(self, run: ActiveRun) -> None:
        with self._lock:
            self._runs[run.thread_id] = run

    def get(self, thread_id: str) -> Optional[ActiveRun]:
        with self._lock:
            return self._runs.get(thread_id)

    def stream_run(
        self,
        query: str,
        *,
        enable_hitl: bool = False,
        thread_id: str | None = None,
        autonomy_level: str | None = None,
    ) -> Generator[str, None, None]:
        """Yield SSE `data:` lines for a full multi-agent run."""
        from utils.constants import DEFAULT_AUTONOMY_LEVEL
        from utils.governance import normalize_autonomy_level

        tid = thread_id or f"{DEFAULT_THREAD_ID}-ui-{uuid.uuid4().hex[:10]}"
        level = normalize_autonomy_level(autonomy_level or DEFAULT_AUTONOMY_LEVEL)
        # HITL checkbox forces human gates on; unchecked keeps selected autonomy as-is
        human_review = bool(enable_hitl) or level != "L4"
        if not enable_hitl and level in {"L0", "L1", "L2", "L3"}:
            # Still honor autonomy-driven gates even if legacy checkbox is off
            human_review = True
        if level == "L4":
            human_review = False

        graph = MultiAgentGraph(
            enable_checkpoints=True,
            enable_human_review=human_review,
            autonomy_level=level,
        )
        run = ActiveRun(
            thread_id=tid,
            graph=graph,
            enable_hitl=human_review,
            query=query,
            autonomy_level=level,
        )
        self._register(run)
        config = {
            "configurable": {"thread_id": tid},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }

        yield self._sse(
            "run_started",
            {
                "thread_id": tid,
                "query": query,
                "enable_hitl": human_review,
                "autonomy_level": level,
                "model": active_model_label(),
            },
        )

        try:
            yield from self._stream_graph(graph, query, config, tid)
        except Exception as exc:  # noqa: BLE001
            yield self._sse(
                "error",
                {"thread_id": tid, "message": str(exc)},
            )

    def stream_resume(
        self,
        thread_id: str,
        decision: str,
    ) -> Generator[str, None, None]:
        run = self.get(thread_id)
        if not run:
            yield self._sse(
                "error",
                {"thread_id": thread_id, "message": "Unknown or expired run session"},
            )
            return

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }
        yield self._sse(
            "resume_started",
            {"thread_id": thread_id, "decision": decision},
        )

        try:
            with run.lock:
                yield from self._stream_graph(
                    run.graph,
                    Command(resume=decision),
                    config,
                    thread_id,
                )
        except Exception as exc:  # noqa: BLE001
            yield self._sse(
                "error",
                {"thread_id": thread_id, "message": str(exc)},
            )

    def _stream_graph(
        self,
        graph: MultiAgentGraph,
        input_payload: Any,
        config: dict,
        thread_id: str,
    ) -> Generator[str, None, None]:
        last_node: str | None = None
        step_index = 0
        for update in graph.graph.stream(
            input_payload
            if not isinstance(input_payload, str)
            else graph._initial_state(input_payload),
            config,
            stream_mode="updates",
        ):
            node_name = next(iter(update.keys()))
            payload = to_jsonable(update[node_name])
            preview = self._node_preview(node_name, payload)
            step_index += 1

            if last_node and last_node != node_name:
                yield self._sse(
                    "handoff",
                    {
                        "thread_id": thread_id,
                        "from": last_node,
                        "to": node_name,
                        "step": step_index,
                        "reason": self._handoff_reason(last_node, node_name, preview),
                        "state_summary": preview.get("state_summary"),
                    },
                )

            yield self._sse(
                "node",
                {
                    "thread_id": thread_id,
                    "node": node_name,
                    "step": step_index,
                    "from_node": last_node,
                    "payload": preview,
                },
            )
            last_node = node_name

        snapshot = graph.get_state(config)
        values = snapshot.values if snapshot else {}
        interrupts = self._extract_interrupts(snapshot)

        if interrupts:
            interrupt_payload = to_jsonable(interrupts[0])
            yield self._sse(
                "handoff",
                {
                    "thread_id": thread_id,
                    "from": last_node or "agent",
                    "to": "human",
                    "step": step_index + 1,
                    "reason": "Governance / HITL gate requires human decision",
                    "state_summary": (
                        interrupt_payload.get("prompt")
                        if isinstance(interrupt_payload, dict)
                        else str(interrupt_payload)
                    ),
                },
            )
            yield self._sse(
                "interrupt",
                {
                    "thread_id": thread_id,
                    "payload": interrupt_payload,
                    "from_node": last_node,
                },
            )
            return

        if last_node and last_node != "synthesizer":
            yield self._sse(
                "handoff",
                {
                    "thread_id": thread_id,
                    "from": last_node,
                    "to": "complete",
                    "step": step_index + 1,
                    "reason": "Run finished",
                },
            )

        summary = summarize_state(values if isinstance(values, dict) else {})
        yield self._sse(
            "final",
            {
                "thread_id": thread_id,
                "result": summary,
                "report": format_run_report(values if isinstance(values, dict) else {}),
                "current_agent": "complete",
            },
        )
        yield self._sse("done", {"thread_id": thread_id})

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    @staticmethod
    def _handoff_reason(from_node: str, to_node: str, preview: dict) -> str:
        mapping = {
            ("planner", "dispatch"): "Plan ready — dispatching work",
            ("dispatch", "researcher"): "Routed research task",
            ("dispatch", "coder"): "Routed coding task",
            ("dispatch", "synthesizer"): "No pending work — synthesize",
            ("researcher", "reviewer"): "Research complete — quality review",
            ("coder", "reviewer"): "Code complete — quality review",
            ("reviewer", "researcher"): "Revision requested — back to researcher",
            ("reviewer", "coder"): "Approved / next coding task",
            ("reviewer", "synthesizer"): "Reviews complete — final synthesis",
            ("synthesizer", "complete"): "Delivery packaged",
        }
        if preview.get("latest_action", {}).get("governance_escalation"):
            return "Governance escalation before handoff"
        return mapping.get((from_node, to_node), f"Handoff {from_node} → {to_node}")

    @staticmethod
    def _node_preview(node: str, payload: Any) -> dict:
        if not isinstance(payload, dict):
            return {"summary": str(payload)[:400], "state_summary": str(payload)[:240]}
        preview: Dict[str, Any] = {"node": node, "status": "completed"}
        if payload.get("final_output"):
            preview["final_output"] = str(payload["final_output"])[:500]
        if payload.get("tasks"):
            preview["tasks"] = payload["tasks"]
            preview["task_count"] = len(payload["tasks"])
        if payload.get("compliance"):
            preview["compliance"] = payload["compliance"]
        if payload.get("governance"):
            preview["governance"] = payload["governance"]
        if payload.get("autonomy_level"):
            preview["autonomy_level"] = payload["autonomy_level"]
        if payload.get("current_task_id"):
            preview["current_task_id"] = payload["current_task_id"]
        if payload.get("research_findings"):
            latest = payload["research_findings"][-1]
            preview["artifact"] = {
                "type": "research",
                "sources": latest.get("sources") or [],
                "excerpt": str(latest.get("findings") or "")[:280],
            }
        if payload.get("code_artifacts"):
            latest = payload["code_artifacts"][-1]
            preview["artifact"] = {
                "type": "code",
                "language": latest.get("language"),
                "excerpt": str(latest.get("code") or "")[:280],
                "usage": str(latest.get("usage") or "")[:160],
            }
        if payload.get("review_feedback"):
            latest = payload["review_feedback"][-1]
            preview["review"] = {
                "approved": latest.get("approved"),
                "score": latest.get("score"),
                "decision": latest.get("decision"),
                "feedback": str(latest.get("feedback") or "")[:240],
            }
        history = payload.get("agent_history") or []
        if history:
            preview["latest_action"] = history[-1]
        messages = payload.get("messages") or []
        if messages:
            last = messages[-1]
            content = last.get("content") if isinstance(last, dict) else str(last)
            preview["message"] = str(content)[:500]

        # Compact state line for step view
        if node == "planner":
            preview["state_summary"] = (
                f"Created {preview.get('task_count', 0)} task(s)"
            )
        elif node == "dispatch":
            preview["state_summary"] = "Selected next worker agent"
        elif node == "researcher":
            sources = (preview.get("artifact") or {}).get("sources") or []
            preview["state_summary"] = f"Research done · {len(sources)} source(s)"
        elif node == "coder":
            lang = (preview.get("artifact") or {}).get("language") or "code"
            preview["state_summary"] = f"Generated {lang} artifact"
        elif node == "reviewer":
            review = preview.get("review") or {}
            preview["state_summary"] = (
                f"Review {review.get('decision', 'n/a')} · score={review.get('score', 'n/a')}"
            )
        elif node == "synthesizer":
            preview["state_summary"] = "Final delivery assembled"
        else:
            preview["state_summary"] = (
                preview.get("message") or preview.get("summary") or f"{node} updated"
            )[:180]
        return preview

    @staticmethod
    def _extract_interrupts(snapshot) -> list:
        if snapshot is None:
            return []
        values = []
        tasks = getattr(snapshot, "tasks", None) or ()
        for task in tasks:
            interrupts = getattr(task, "interrupts", None) or ()
            for item in interrupts:
                values.append(getattr(item, "value", item))
        if values:
            return values
        interrupts = getattr(snapshot, "interrupts", None) or ()
        return [getattr(item, "value", item) for item in interrupts]


console_service = AgentConsoleService()
