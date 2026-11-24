"""Action catalog for Fields of Fire, loaded from the game config file."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "fof" / "fields_of_fire_actions.json"


@lru_cache(maxsize=1)
def load_actions() -> list[dict[str, Any]]:
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("fields_of_fire_actions.json must contain a list of actions")
    return data


def _normalize(name: str) -> str:
    return name.rstrip("¹²³⁴⁵⁶⁷⁸⁹⁰").strip()


def action_by_name(name: str) -> dict[str, Any] | None:
    target = _normalize(name)
    for action in load_actions():
        if _normalize(str(action.get("name", ""))) == target:
            return action
    return None


def action_by_id(action_id: str) -> dict[str, Any] | None:
    for action in load_actions():
        if action.get("id") == action_id:
            return action
    return None


def button_text(name_or_id: str) -> str | None:
    action = action_by_name(name_or_id) or action_by_id(name_or_id)
    return action.get("button_text") if action else None