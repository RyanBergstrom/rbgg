from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional, Set

ShapeType = Literal["rectangle", "circle", "hex", "diamond"]
VALID_SHAPES: Set[str] = {"rectangle", "circle", "hex", "diamond"}


# ── Visual Component Config ────────────────────────────────────────────

@dataclass
class GridConfig:
    """Grid layout for location labeling (e.g. 'A1', '3,5').

    This is NOT a visual grid — it defines row/column count for
    coordinate mapping. Cell sizing is a frontend rendering concern.
    """
    rows: int
    columns: int

    def __post_init__(self) -> None:
        if self.rows < 1:
            raise ValueError('grid rows must be >= 1')
        if self.columns < 1:
            raise ValueError('grid columns must be >= 1')

    def to_dict(self) -> dict[str, Any]:
        return {"rows": self.rows, "columns": self.columns}


@dataclass
class ComponentConfig:
    """A visual component placed on a panel.

    Core properties available to all games. Game-specific data lives in
    the validator's game_data, not here.
    """
    name: str
    shape: str = "rectangle"
    color: Optional[str] = None
    background_image: Optional[str] = None
    z_index: int = 0
    grid: Optional[GridConfig] = None
    # Interaction properties
    stackable: bool = False
    stack_name: Optional[str] = None
    rotate: Optional[int] = None
    clickable: bool = True
    hover_text: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError('component name must be non-empty')
        if self.shape not in VALID_SHAPES:
            raise ValueError(
                f'component shape must be one of {VALID_SHAPES}, got \'{self.shape}\''
            )
        if self.color is not None and self.background_image is not None:
            raise ValueError('component cannot have both color and background_image')
        if self.grid is not None and not isinstance(self.grid, GridConfig):
            if isinstance(self.grid, dict):
                self.grid = GridConfig(**self.grid)
            else:
                raise ValueError('grid must be a GridConfig or dict')
        if self.rotate is not None and self.rotate < 1:
            raise ValueError('rotate must be null or >= 1')

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "shape": self.shape,
            "z_index": self.z_index,
            "clickable": self.clickable,
        }
        if self.color is not None:
            d["color"] = self.color
        if self.background_image is not None:
            d["background_image"] = self.background_image
        if self.grid is not None:
            d["grid"] = self.grid.to_dict()
        if self.stackable:
            d["stackable"] = True
        if self.stack_name is not None:
            d["stack_name"] = self.stack_name
        if self.rotate is not None:
            d["rotate"] = self.rotate
        if self.hover_text is not None:
            d["hover_text"] = self.hover_text
        return d


@dataclass
class PanelConfig:
    """A screen window / layout region that holds components."""
    panel_id: str
    name: str
    required: bool = False
    components: dict[str, ComponentConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.panel_id or not self.panel_id.strip():
            raise ValueError('panel_id must be non-empty')
        if not self.name or not self.name.strip():
            raise ValueError('panel name must be non-empty')
        for comp_id, comp in self.components.items():
            if isinstance(comp, dict):
                self.components[comp_id] = ComponentConfig(**comp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "name": self.name,
            "required": self.required,
            "components": {k: v.to_dict() for k, v in self.components.items()},
        }


# ── Difficulty Config ────────────────────────────────────────────────

@dataclass
class DifficultyConfig:
    """AI difficulty levels for a game.

    Each level maps a name (e.g. 'easy') to an iteration count for MCTS.
    The ``default`` key specifies which level to use when none is selected.
    """
    levels: dict[str, int] = field(default_factory=dict)
    default: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = dict(self.levels)
        d["default"] = self.default
        return d


# ── Turn / Phase Config ────────────────────────────────────────────────

@dataclass
class ConfirmConfig:
    """Settings for a phase's confirm button."""
    required: bool = False
    name: str = "Confirm"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"required": self.required}
        if self.name:
            d["name"] = self.name
        if self.description:
            d["description"] = self.description
        return d


@dataclass
class PhaseConfig:
    """A single step in a turn — acts as a UI state machine.

    At the start of each phase, the frontend calls the legal moves API
    to determine what the player can do. The phase controls which UI
    elements are interactive.
    """
    name: str
    text: str = ""
    order: int = 0
    confirm: Optional[ConfirmConfig] = None
    timeout_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError('phase name must be non-empty')
        if self.confirm is not None and not isinstance(self.confirm, ConfirmConfig):
            if isinstance(self.confirm, dict):
                self.confirm = ConfirmConfig(**self.confirm)
            else:
                raise ValueError('confirm must be a ConfirmConfig or dict')

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "text": self.text,
            "order": self.order,
        }
        if self.confirm is not None:
            d["confirm"] = self.confirm.to_dict()
        if self.timeout_seconds is not None:
            d["timeout_seconds"] = self.timeout_seconds
        return d


@dataclass
class TurnConfig:
    """A sequence of phases that a player goes through before passing.

    Each player runs through the same turn sequence. For checkers:
    [Player_Turn, Pass_Turn]. For more complex games, a turn might
    have more phases.
    """
    name: str
    phases: List[PhaseConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError('turn name must be non-empty')
        # Normalize dict phases to PhaseConfig
        normalized: List[PhaseConfig] = []
        for p in self.phases:
            if isinstance(p, dict):
                normalized.append(PhaseConfig(**p))
            else:
                normalized.append(p)
        self.phases = normalized

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "phases": [p.to_dict() for p in self.phases],
        }


@dataclass
class RoundConfig:
    """A top-level game segment containing turns.

    For simple games like checkers, there's one round with one turn type.
    For complex games like Terraforming Mars, there might be multiple
    rounds (e.g., "Card Selection" round, then "Playing Cards" round).
    """
    name: str
    turns: List[TurnConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError('round name must be non-empty')
        normalized: List[TurnConfig] = []
        for t in self.turns:
            if isinstance(t, dict):
                normalized.append(TurnConfig(**t))
            else:
                normalized.append(t)
        self.turns = normalized

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "turns": [t.to_dict() for t in self.turns],
        }


# ── Game Config (top level) ───────────────────────────────────────────

@dataclass
class GameConfig:
    panels: dict[str, PanelConfig] = field(default_factory=dict)
    rounds: List[RoundConfig] = field(default_factory=list)
    min_players: Optional[int] = None
    max_players: Optional[int] = None
    cover_image: Optional[str] = None
    difficulty: Optional[DifficultyConfig] = None
    hover_zoom: bool = True

    def __post_init__(self) -> None:
        required_panel_ids: Set[str] = {'game_progress', 'main_board'}
        present_panel_ids: Set[str] = set(self.panels.keys())
        missing: Set[str] = required_panel_ids - present_panel_ids
        if missing:
            raise ValueError(f'Game config must include required panels: {missing}')

        # Normalize panel dicts
        for panel_id, panel in self.panels.items():
            if isinstance(panel, dict):
                self.panels[panel_id] = PanelConfig(**panel)

        # Normalize round dicts
        normalized: List[RoundConfig] = []
        for r in self.rounds:
            if isinstance(r, dict):
                normalized.append(RoundConfig(**r))
            else:
                normalized.append(r)
        self.rounds = normalized

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "panels": {k: v.to_dict() for k, v in self.panels.items()},
            "rounds": [r.to_dict() for r in self.rounds],
        }
        if self.min_players is not None:
            d["min_players"] = self.min_players
        if self.max_players is not None:
            d["max_players"] = self.max_players
        if self.cover_image is not None:
            d["cover_image"] = self.cover_image
        if self.difficulty is not None:
            d["difficulty"] = self.difficulty.to_dict()
        d["hover_zoom"] = self.hover_zoom
        return d
