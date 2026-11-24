"""Lab execution adapters that emit SSE event payloads for Agent Desk."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List

from ui.labs import get_lab
from ui.serializers import to_jsonable
from utils.llm import active_model_label

LABS_ROOT = Path(__file__).resolve().parents[2]
DAY2_ROOT = Path(__file__).resolve().parents[1]
_CONFLICT_TOP_LEVEL = ("app", "state", "nodes", "graph", "utils", "tools", "agents")
_SUPPORT_RUNS: Dict[str, Dict[str, Any]] = {}
_DAY3_BRIDGE = r"""
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path="../.env.azure", override=False)
os.environ.setdefault("LLM_PROVIDER", "azure")
os.environ.setdefault("REDIS_ENABLED", "false")

from app.agent_service import get_agent_service

query = sys.argv[1]
session_id = sys.argv[2]
result = asyncio.run(get_agent_service().process_query(query=query, session_id=session_id))
print(json.dumps(result))
"""


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _lab_python(lab_dir: Path) -> str:
    candidate = lab_dir / "venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


@contextmanager
def _isolated_lab_imports(lab_dir: Path, extra_keep: Iterable[Path] = ()):
    """Temporarily prefer a lab directory on sys.path without permanently breaking Day2."""
    saved_path = list(sys.path)
    snapped: Dict[str, Any] = {}
    for name in list(sys.modules):
        top = name.split(".", 1)[0]
        if top in _CONFLICT_TOP_LEVEL:
            snapped[name] = sys.modules.pop(name)

    keep = {str(DAY2_ROOT), str(lab_dir), *[str(path) for path in extra_keep]}
    sys.path = [str(lab_dir)] + [entry for entry in saved_path if entry not in keep]
    for path in [lab_dir, DAY2_ROOT, *extra_keep]:
        value = str(path)
        if value not in sys.path:
            sys.path.append(value)
    importlib.invalidate_caches()
    try:
        yield
    finally:
        for name in list(sys.modules):
            top = name.split(".", 1)[0]
            if top in _CONFLICT_TOP_LEVEL:
                sys.modules.pop(name, None)
        sys.path[:] = saved_path
        sys.modules.update({key: value for key, value in snapped.items() if value is not None})
        importlib.invalidate_caches()


def stream_lab_run(
    lab_id: str,
    query: str,
    *,
    enable_hitl: bool = False,
    thread_id: str | None = None,
) -> Generator[str, None, None]:
    lab = get_lab(lab_id)
    tid = thread_id or f"{lab_id}-{uuid.uuid4().hex[:10]}"
    hitl = bool(enable_hitl and lab.get("supports_hitl"))

    try:
        if lab_id == "day2_advanced":
            yield from _run_day2(
                query,
                enable_hitl=hitl,
                thread_id=tid,
                lab=lab,
            )
        elif lab_id == "customer_support":
            yield _sse(
                "run_started",
                {
                    "thread_id": tid,
                    "lab_id": lab["id"],
                    "lab_name": lab["name"],
                    "query": query,
                    "enable_hitl": hitl,
                    "model": active_model_label(),
                    "flow": lab.get("flow", []),
                },
            )
            yield from _run_customer_support(query, enable_hitl=hitl, thread_id=tid)
        elif lab_id in {"day3_medium", "day3_advanced"}:
            yield _sse(
                "run_started",
                {
                    "thread_id": tid,
                    "lab_id": lab["id"],
                    "lab_name": lab["name"],
                    "query": query,
                    "enable_hitl": False,
                    "model": active_model_label(),
                    "flow": lab.get("flow", []),
                },
            )
            yield from _run_day3_service(
                lab_dir=LABS_ROOT / ("Day3_Medium" if lab_id == "day3_medium" else "Day3_Advanced"),
                query=query,
                thread_id=tid,
                lab_id=lab_id,
            )
        else:
            yield _sse("error", {"thread_id": tid, "message": f"Unsupported lab: {lab_id}"})
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"thread_id": tid, "message": str(exc)})


def stream_lab_resume(
    lab_id: str,
    thread_id: str,
    decision: str,
) -> Generator[str, None, None]:
    yield _sse(
        "resume_started",
        {"thread_id": thread_id, "lab_id": lab_id, "decision": decision},
    )
    try:
        if lab_id == "day2_advanced":
            from ui.service import console_service

            yield from console_service.stream_resume(thread_id, decision)
            return
        if lab_id == "customer_support":
            yield from _resume_customer_support(thread_id, decision)
            return
        yield _sse(
            "error",
            {
                "thread_id": thread_id,
                "message": f"HITL resume is not supported for lab '{lab_id}'",
            },
        )
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"thread_id": thread_id, "message": str(exc)})


def _run_day2(
    query: str,
    *,
    enable_hitl: bool,
    thread_id: str,
    lab: dict,
) -> Generator[str, None, None]:
    from ui.service import console_service

    # Inject lab metadata into the first event by wrapping the generator
    started = False
    for chunk in console_service.stream_run(
        query, enable_hitl=enable_hitl, thread_id=thread_id
    ):
        if not started and chunk.startswith("event: run_started"):
            started = True
            data = {
                "thread_id": thread_id,
                "lab_id": lab["id"],
                "lab_name": lab["name"],
                "query": query,
                "enable_hitl": enable_hitl,
                "model": active_model_label(),
                "flow": lab.get("flow", []),
            }
            yield _sse("run_started", data)
            continue
        yield chunk


def _run_day3_service(
    *,
    lab_dir: Path,
    query: str,
    thread_id: str,
    lab_id: str,
) -> Generator[str, None, None]:
    yield _sse("node", {"node": "guardrails", "payload": {"message": "Validating query"}})
    yield _sse("node", {"node": "agent", "payload": {"message": "Generating response"}})

    env = os.environ.copy()
    env.setdefault("LLM_PROVIDER", "azure")
    env.setdefault("REDIS_ENABLED", "false")
    completed = subprocess.run(
        [_lab_python(lab_dir), "-c", _DAY3_BRIDGE, query, thread_id],
        cwd=str(lab_dir),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Day3 lab failed").strip()
        raise RuntimeError(detail[-1200:])

    line = completed.stdout.strip().splitlines()[-1]
    result = json.loads(line)
    metadata = result.get("metadata") or {}
    compliance = metadata.get("compliance") or {"verdict": "pass"}
    node = "compliance_gate" if lab_id == "day3_advanced" else "response"
    yield _sse(
        "node",
        {
            "node": node,
            "payload": {"message": f"Compliance: {compliance.get('verdict', 'n/a')}"},
        },
    )
    report = "\n".join(
        [
            "Enterprise Run Report",
            f"- Lab: {lab_id}",
            f"- Session: {thread_id}",
            f"- Model: {metadata.get('model', active_model_label())}",
            f"- Duration s: {result.get('execution_time', 'n/a')}",
            f"- Compliance: {compliance.get('verdict', 'n/a')}",
        ]
    )
    yield _sse(
        "final",
        {
            "thread_id": thread_id,
            "lab_id": lab_id,
            "result": {
                "run_id": metadata.get("run_id", thread_id),
                "final_output": result.get("response", ""),
                "tasks": [],
                "compliance": compliance,
                "metrics": {
                    "duration_ms": round(float(result.get("execution_time") or 0) * 1000, 2)
                },
                "policy_violations": metadata.get("policy_violations") or [],
            },
            "report": report,
        },
    )
    yield _sse("done", {"thread_id": thread_id, "lab_id": lab_id})


def _run_customer_support(
    query: str, *, enable_hitl: bool, thread_id: str
) -> Generator[str, None, None]:
    support_root = LABS_ROOT / "CustomerSupportAgent"
    with _isolated_lab_imports(support_root):
        from graph import create_email_agent_graph, default_run_config

        graph = create_email_agent_graph(enable_checkpoints=True)
        config = default_run_config(thread_id)
        _SUPPORT_RUNS[thread_id] = {
            "graph": graph,
            "config": config,
            "lab_dir": str(support_root),
        }
        initial_state = {
            "email_content": query,
            "sender_email": "customer@example.com",
            "email_id": thread_id,
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
            "run_id": thread_id,
            "run_metadata": {},
            "metrics": {},
            "audit_trail": [],
        }
        # Consume stream inside isolated context so imports stay valid
        chunks: List[str] = list(
            _stream_support_graph(graph, initial_state, config, thread_id)
        )
    yield from chunks


def _resume_customer_support(
    thread_id: str, decision: str
) -> Generator[str, None, None]:
    session = _SUPPORT_RUNS.get(thread_id)
    if not session:
        yield _sse(
            "error",
            {"thread_id": thread_id, "message": "Unknown or expired support session"},
        )
        return
    support_root = Path(session["lab_dir"])
    with _isolated_lab_imports(support_root):
        from langgraph.types import Command

        graph = session["graph"]
        config = session["config"]
        chunks = list(_stream_support_graph(graph, Command(resume=decision), config, thread_id))
    yield from chunks


def _stream_support_graph(
    graph, input_payload, config, thread_id: str
) -> Generator[str, None, None]:
    for update in graph.stream(input_payload, config, stream_mode="updates"):
        node_name = next(iter(update.keys()))
        payload = to_jsonable(update[node_name])
        message = ""
        if isinstance(payload, dict):
            if payload.get("final_response"):
                message = str(payload["final_response"])[:240]
            elif payload.get("draft_response"):
                message = "Draft generated"
            elif payload.get("classification"):
                classification = payload["classification"]
                message = (
                    f"{classification.get('intent')} / {classification.get('urgency')}"
                )
            elif payload.get("messages"):
                last = payload["messages"][-1]
                message = str(last.get("content") if isinstance(last, dict) else last)[
                    :240
                ]
        yield _sse(
            "node",
            {"node": node_name, "payload": {"message": message or "updated"}},
        )

    snapshot = graph.get_state(config)
    interrupts = _extract_interrupts(snapshot)
    if interrupts:
        yield _sse(
            "interrupt",
            {
                "thread_id": thread_id,
                "lab_id": "customer_support",
                "payload": to_jsonable(interrupts[0]),
            },
        )
        return

    values = snapshot.values if snapshot else {}
    compliance = values.get("compliance") or {}
    classification = values.get("classification") or {}
    report = "\n".join(
        [
            "Enterprise Run Report",
            "- Lab: customer_support",
            f"- Thread: {thread_id}",
            f"- Intent: {classification.get('intent', 'n/a')}",
            f"- Urgency: {classification.get('urgency', 'n/a')}",
            f"- SLA hours: {classification.get('sla_hours', 'n/a')}",
            f"- Compliance: {compliance.get('verdict', 'n/a')}",
            f"- Audit events: {len(values.get('audit_trail') or [])}",
        ]
    )
    yield _sse(
        "final",
        {
            "thread_id": thread_id,
            "lab_id": "customer_support",
            "result": {
                "run_id": values.get("run_id", thread_id),
                "final_output": values.get("final_response") or "",
                "tasks": [],
                "compliance": compliance,
                "metrics": values.get("metrics") or {},
                "policy_violations": values.get("policy_violations") or [],
                "classification": classification,
            },
            "report": report,
        },
    )
    yield _sse("done", {"thread_id": thread_id, "lab_id": "customer_support"})


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
