"""Settings routes — read/write application settings to a JSON file."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "hover_zoom_percent": 150,
}


def _load_settings() -> dict[str, Any]:
    """Load settings from file, falling back to defaults."""
    if SETTINGS_FILE.is_file():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {**DEFAULT_SETTINGS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return {**DEFAULT_SETTINGS}


def _save_settings(settings: dict[str, Any]) -> None:
    """Write settings to file."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


@router.get("/", response_model=dict)
def get_settings() -> dict[str, Any]:
    """Return current application settings."""
    return _load_settings()


@router.put("/", response_model=dict)
def update_settings(body: dict = Body(...)) -> dict[str, Any]:
    """Update application settings."""
    current = _load_settings()
    current.update(body)
    _save_settings(current)
    return current
