"""Lightweight audit logging for support runs."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


LOGGER = logging.getLogger("support_enterprise")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


@dataclass
class RunMetrics:
    started_at: str
    ended_at: Optional[str] = None
    duration_ms: Optional[float] = None
    node_timings_ms: Dict[str, float] = field(default_factory=dict)


class RunContext:
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        self.metrics = RunMetrics(started_at=_utc_now())
        self.events: List[Dict[str, Any]] = []
        self._t0 = time.perf_counter()

    def log(self, agent: str, action: str, **details: Any) -> None:
        event = {
            "run_id": self.run_id,
            "agent": agent,
            "action": action,
            "timestamp": _utc_now(),
            **{k: v for k, v in details.items() if v is not None},
        }
        self.events.append(event)
        LOGGER.info(json.dumps(event, default=str))

    def time_node(self, node: str, elapsed_ms: float) -> None:
        self.metrics.node_timings_ms[node] = round(
            self.metrics.node_timings_ms.get(node, 0.0) + elapsed_ms, 2
        )

    def finalize(self) -> Dict[str, Any]:
        self.metrics.ended_at = _utc_now()
        self.metrics.duration_ms = round((time.perf_counter() - self._t0) * 1000, 2)
        return {
            "run_id": self.run_id,
            "metrics": asdict(self.metrics),
            "audit_trail": self.events,
        }
