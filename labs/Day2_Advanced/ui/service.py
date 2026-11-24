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
    lock: threading.Lock = field(default_factory=threading.Lock)


class AgentConsoleService:
    """Keeps in-memory run sessions so HITL resume works from the UI."""

    def __init__(self) -> None:
        self._runs: Dict[str, ActiveRun] = {}
        self._lock = threading.Lock()

    def config(self) -> dict:
        return {
            "model": active_model_label(),
            "provider": active_model_label().split("/", 1)[0],
            "hitl_default": False,
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
    ) -> Generator[str, None, None]:
        """Yield SSE `data:` lines for a full multi-agent run."""
        tid = thread_id or f"{DEFAULT_THREAD_ID}-ui-{uuid.uuid4().hex[:10]}"
        graph = MultiAgentGraph(
            enable_checkpoints=True,
            enable_human_review=enable_hitl,
        )
        run = ActiveRun(
            thread_id=tid,
            graph=graph,
            enable_hitl=enable_hitl,
            query=query,
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
                "enable_hitl": enable_hitl,
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
        for update in graph.graph.stream(
            input_payload
            if not isinstance(input_payload, str)
            else graph._initial_state(input_payload),
            config,
            stream_mode="updates",
        ):
            node_name = next(iter(update.keys()))
            payload = to_jsonable(update[node_name])
            yield self._sse(
                "node",
                {
                    "node": node_name,
                    "payload": self._node_preview(node_name, payload),
                },
            )

        snapshot = graph.get_state(config)
        values = snapshot.values if snapshot else {}
        interrupts = self._extract_interrupts(snapshot)

        if interrupts:
            yield self._sse(
                "interrupt",
                {
                    "thread_id": thread_id,
                    "payload": to_jsonable(interrupts[0]),
                },
            )
            return

        summary = summarize_state(values if isinstance(values, dict) else {})
        yield self._sse(
            "final",
            {
                "thread_id": thread_id,
                "result": summary,
                "report": format_run_report(values if isinstance(values, dict) else {}),
            },
        )
        yield self._sse("done", {"thread_id": thread_id})

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    @staticmethod
    def _node_preview(node: str, payload: Any) -> dict:
        if not isinstance(payload, dict):
            return {"summary": str(payload)[:400]}
        preview: Dict[str, Any] = {"node": node}
        if payload.get("final_output"):
            preview["final_output"] = str(payload["final_output"])[:500]
        if payload.get("tasks"):
            preview["tasks"] = payload["tasks"]
        if payload.get("compliance"):
            preview["compliance"] = payload["compliance"]
        history = payload.get("agent_history") or []
        if history:
            preview["latest_action"] = history[-1]
        messages = payload.get("messages") or []
        if messages:
            last = messages[-1]
            content = last.get("content") if isinstance(last, dict) else str(last)
            preview["message"] = str(content)[:500]
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
