"""Structured observability and audit helpers for enterprise agent runs."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("day2_enterprise")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


LOGGER = configure_logging()


@dataclass
class AuditEvent:
    run_id: str
    agent: str
    action: str
    timestamp: str
    status: str = "ok"
    task_id: Optional[str] = None
    duration_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunMetrics:
    started_at: str
    ended_at: Optional[str] = None
    duration_ms: Optional[float] = None
    llm_calls: int = 0
    retries: int = 0
    guardrail_blocks: int = 0
    policy_violations: int = 0
    node_timings_ms: Dict[str, float] = field(default_factory=dict)


class RunContext:
    """Correlation + audit trail for a single multi-agent execution."""

    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        self.metrics = RunMetrics(started_at=_utc_now())
        self.events: List[AuditEvent] = []
        self._t0 = time.perf_counter()

    def log(
        self,
        agent: str,
        action: str,
        *,
        status: str = "ok",
        task_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **details: Any,
    ) -> AuditEvent:
        event = AuditEvent(
            run_id=self.run_id,
            agent=agent,
            action=action,
            timestamp=_utc_now(),
            status=status,
            task_id=task_id,
            duration_ms=duration_ms,
            details={k: v for k, v in details.items() if v is not None},
        )
        self.events.append(event)
        payload = {
            "run_id": event.run_id,
            "agent": event.agent,
            "action": event.action,
            "status": event.status,
            "task_id": event.task_id,
            "duration_ms": event.duration_ms,
            **event.details,
        }
        level = logging.WARNING if status != "ok" else logging.INFO
        LOGGER.log(level, json.dumps(payload, default=str))
        return event

    def increment(self, field_name: str, amount: int = 1) -> None:
        current = getattr(self.metrics, field_name, 0)
        setattr(self.metrics, field_name, int(current) + amount)

    @contextmanager
    def timed(self, node_name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self.metrics.node_timings_ms[node_name] = round(
                self.metrics.node_timings_ms.get(node_name, 0.0) + elapsed,
                2,
            )

    def finalize(self) -> Dict[str, Any]:
        self.metrics.ended_at = _utc_now()
        self.metrics.duration_ms = round((time.perf_counter() - self._t0) * 1000, 2)
        return {
            "run_id": self.run_id,
            "metrics": asdict(self.metrics),
            "audit_trail": [asdict(event) for event in self.events],
        }


def format_run_report(state: Dict[str, Any]) -> str:
    """Human-readable enterprise run report for demos/CLI."""
    meta = state.get("run_metadata") or {}
    metrics = state.get("metrics") or meta.get("metrics") or {}
    compliance = state.get("compliance") or {}
    governance = state.get("governance") or {}
    lines = [
        "Enterprise Run Report",
        f"- Run ID: {meta.get('run_id') or state.get('run_id', 'n/a')}",
        f"- Autonomy: {state.get('autonomy_level') or governance.get('autonomy_level', 'n/a')}",
        f"- Governance escalations: {governance.get('escalations', 0)}",
        f"- Duration ms: {metrics.get('duration_ms', 'n/a')}",
        f"- LLM calls: {metrics.get('llm_calls', 0)}",
        f"- Retries: {metrics.get('retries', 0)}",
        f"- Guardrail blocks: {metrics.get('guardrail_blocks', 0)}",
        f"- Policy violations: {metrics.get('policy_violations', 0)}",
        f"- Compliance: {compliance.get('verdict', 'n/a')}",
    ]
    timings = metrics.get("node_timings_ms") or {}
    if timings:
        lines.append("- Node timings (ms):")
        for node, ms in timings.items():
            lines.append(f"  - {node}: {ms}")
    violations = state.get("policy_violations") or []
    if violations:
        lines.append("- Violations:")
        for item in violations[:8]:
            lines.append(f"  - {item}")
    return "\n".join(lines)
