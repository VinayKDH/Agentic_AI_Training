"""Lab catalog helpers for the multi-lab Agent Desk UI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.constants import UI_DEFAULT_LAB_ID, UI_LABS


def list_labs() -> List[Dict[str, Any]]:
    return [dict(lab) for lab in UI_LABS]


def get_lab(lab_id: str | None) -> Dict[str, Any]:
    target = (lab_id or UI_DEFAULT_LAB_ID).strip()
    for lab in UI_LABS:
        if lab["id"] == target:
            return dict(lab)
    raise KeyError(f"Unknown lab: {target}")


def default_lab_id() -> str:
    return UI_DEFAULT_LAB_ID
