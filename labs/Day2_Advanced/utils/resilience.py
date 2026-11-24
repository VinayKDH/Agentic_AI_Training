"""Retry and resilience helpers for enterprise LLM/tool calls."""

from __future__ import annotations

import random
import time
from typing import Callable, Optional, TypeVar

from utils.constants import (
    LLM_MAX_RETRIES,
    LLM_RETRY_BASE_DELAY_SECONDS,
    LLM_RETRY_MAX_DELAY_SECONDS,
)

T = TypeVar("T")

_RETRYABLE_MARKERS = (
    "rate limit",
    "timeout",
    "temporar",
    "unavailable",
    "429",
    "500",
    "502",
    "503",
    "504",
    "connection",
    "overloaded",
)


def _is_retryable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MARKERS)


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = LLM_MAX_RETRIES,
    operation: str = "llm_call",
    on_retry: Optional[Callable[[int, BaseException], None]] = None,
) -> T:
    """Execute fn with exponential backoff + jitter for transient failures."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - intentional boundary
            attempt += 1
            if attempt > max_retries or not _is_retryable(exc):
                raise
            delay = min(
                LLM_RETRY_MAX_DELAY_SECONDS,
                LLM_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            )
            delay = delay * (0.7 + random.random() * 0.6)
            if on_retry:
                on_retry(attempt, exc)
            time.sleep(delay)
