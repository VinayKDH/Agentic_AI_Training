"""Retry helpers for Day3 Advanced LLM calls."""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from app.constants import (
    LLM_MAX_RETRIES,
    LLM_RETRY_BASE_DELAY_SECONDS,
    LLM_RETRY_MAX_DELAY_SECONDS,
)

T = TypeVar("T")
_RETRYABLE = ("rate limit", "timeout", "temporar", "unavailable", "429", "500", "502", "503", "504", "connection")


def with_retry(fn: Callable[[], T], *, max_retries: int = LLM_MAX_RETRIES) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            message = str(exc).lower()
            retryable = any(marker in message for marker in _RETRYABLE)
            if attempt > max_retries or not retryable:
                raise
            delay = min(
                LLM_RETRY_MAX_DELAY_SECONDS,
                LLM_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
            )
            time.sleep(delay * (0.7 + random.random() * 0.6))
