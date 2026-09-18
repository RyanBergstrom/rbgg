from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

from app.core.config_schema import (
    GameConfig,
    PanelConfig,
    ComponentConfig,
    GridConfig,
    RoundConfig,
    TurnConfig,
    PhaseConfig,
    ConfirmConfig,
    DifficultyConfig,
)


class ConfigLoadError(Exception):
    """Raised when a config file cannot be loaded or validated."""

    def __init__(self, message: str, filepath: str | None = None) -> None:
        self.message = message
        self.filepath = filepath
        super().__init__(self.message)


_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"
_config_cache: dict[str, GameConfig] = {}


def load_config(filepath: str | Path) -> dict[str, Any]:
    """Load a single YAML config file.

    Returns the parsed YAML content as a dict.
    Raises ConfigLoadError if the file cannot be read or parsed.
    """
    path = Path(filepath)
    if not path.is_file():
        raise ConfigLoadError(f"Config file not found: {path}", filepath=str(path))

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"Config file {path} must contain a mapping (dict) at the top level",
            filepath=str(path),
        )

    return data


def load_all_configs(*filepaths: str | Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Load multiple YAML config files stop-on-first-malformed.

    Returns a tuple of (configs_dict, errors_list).
    """
    configs: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for fp in filepaths:
        path = Path(fp)
        try:
            data = load_config(path)
            key = path.stem
            configs[key] = data
        except ConfigLoadError as exc:
            errors.append(exc.message)
            break

    return configs, errors


# ── Parse helpers ──────────────────────────────────────────────────────

def _parse_component(comp_data: dict[str, Any]) -> ComponentConfig:
    """Parse a component dict into a ComponentConfig."""
    grid_data = comp_data.get("grid")
    grid = None
    if grid_data is not None and isinstance(grid_data, dict):
        grid = GridConfig(rows=grid_data["rows"], columns=grid_data["columns"])

    return ComponentConfig(
        name=comp_data.get("name", ""),
        shape=comp_data.get("shape", "rectangle"),
        color=comp_data.get("color"),
        background_image=comp_data.get("background_image"),
        z_index=comp_data.get("z_index", 0),
        grid=grid,
        stackable=comp_data.get("stackable", False),
        stack_name=comp_data.get("stack_name"),
        rotate=comp_data.get("rotate"),
        clickable=comp_data.get("clickable", True),
        hover_text=comp_data.get("hover_text"),
    )


def _parse_panel(panel_data: dict[str, Any], panel_id: str) -> PanelConfig:
    """Parse a panel dict into a PanelConfig with its components."""
    components: dict[str, ComponentConfig] = {}
    for comp_id, comp_data in panel_data.get("components", {}).items():
        if isinstance(comp_data, dict):
            components[comp_id] = _parse_component(comp_data)

    return PanelConfig(
        panel_id=panel_id,
        name=panel_data.get("name", panel_id),
        required=panel_data.get("required", False),
        components=components,
    )


def _parse_confirm(confirm_data: Any) -> ConfirmConfig | None:
    """Parse a confirm config (dict or bool) into ConfirmConfig."""
    if confirm_data is None:
        return None
    if isinstance(confirm_data, bool):
        return ConfirmConfig(required=confirm_data)
    if isinstance(confirm_data, dict):
        return ConfirmConfig(
            required=confirm_data.get("required", False),
            name=confirm_data.get("name", "Confirm"),
            description=confirm_data.get("description", ""),
        )
    return None


def _parse_phase(phase_data: dict[str, Any]) -> PhaseConfig:
    """Parse a phase dict into a PhaseConfig."""
    return PhaseConfig(
        name=phase_data.get("name", ""),
        text=phase_data.get("text", ""),
        order=phase_data.get("order", 0),
        confirm=_parse_confirm(phase_data.get("confirm")),
        timeout_seconds=phase_data.get("timeout_seconds"),
    )


def _parse_turn(turn_data: dict[str, Any]) -> TurnConfig:
    """Parse a turn dict into a TurnConfig with its phases."""
    phases = []
    for phase_data in turn_data.get("phases", []):
        if isinstance(phase_data, dict):
            phases.append(_parse_phase(phase_data))

    return TurnConfig(
        name=turn_data.get("name", ""),
        phases=phases,
    )


def _parse_round(round_data: dict[str, Any]) -> RoundConfig:
    """Parse a round dict into a RoundConfig with its turns."""
    turns = []
    for turn_data in round_data.get("turns", []):
        if isinstance(turn_data, dict):
            turns.append(_parse_turn(turn_data))

    return RoundConfig(
        name=round_data.get("name", ""),
        turns=turns,
    )


# ── Main loader ────────────────────────────────────────────────────────

def load_game_config(game_id: str) -> GameConfig:
    """Load and validate a game config from ``configs/{game_id}.yaml``.

    Results are cached so the file is only read once per process.

    Raises:
        ConfigLoadError: If the file is missing or invalid.
    """
    if game_id in _config_cache:
        return _config_cache[game_id]

    filepath = _CONFIGS_DIR / f"{game_id}.yaml"
    raw = load_config(filepath)

    # Parse panels
    panels: dict[str, PanelConfig] = {}
    for panel_id, panel_data in raw.get("panels", {}).items():
        if isinstance(panel_data, dict):
            panels[panel_id] = _parse_panel(panel_data, panel_id)

    # Parse rounds
    rounds = []
    for round_data in raw.get("rounds", []):
        if isinstance(round_data, dict):
            rounds.append(_parse_round(round_data))

    # Parse difficulty
    difficulty = None
    raw_diff = raw.get("difficulty")
    if raw_diff and isinstance(raw_diff, dict):
        # 'default' key names the default level (must be a string); int values are levels
        default_key = raw_diff.get("default", "")
        if not isinstance(default_key, str):
            default_key = ""
        levels = {k: v for k, v in raw_diff.items() if k != "default" and isinstance(v, int)}
        if not default_key and levels:
            default_key = next(iter(levels))
        difficulty = DifficultyConfig(levels=levels, default=default_key)

    config = GameConfig(
        panels=panels,
        rounds=rounds,
        min_players=raw.get("min_players"),
        max_players=raw.get("max_players"),
        cover_image=raw.get("cover-image"),
        difficulty=difficulty,
        hover_zoom=raw.get("hover_zoom", True),
    )
    _config_cache[game_id] = config
    return config


def clear_config_cache() -> None:
    """Clear the config cache (for testing)."""
    _config_cache.clear()
