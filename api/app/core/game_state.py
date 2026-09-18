from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Topology(str, Enum):
    grid = "grid"
    hex = "hex"
    graph = "graph"


class PlayerInfo(BaseModel):
    player_id: str = Field(..., description="Unique player identifier")
    name: str = Field(..., description="Player display name")
    score: int = Field(0, ge=0, description="Player score")
    color: str = Field(default="#FFFFFF", description="Player color hex")

    @field_validator("color")
    @classmethod
    def color_must_start_with_hash(cls, v: str) -> str:
        if not v.startswith("#"):
            raise ValueError("color must be a hex color starting with #")
        return v


class TurnInfo(BaseModel):
    turn_id: str = Field(..., description="Unique turn identifier")
    player_id: str = Field(..., description="Player who owns this turn")
    topology: Topology = Field(..., description="Board topology")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actions_remaining: int = Field(default=3, ge=0, le=10)


class BoardSpace(BaseModel):
    x: int = Field(..., ge=0, description="X coordinate")
    y: int = Field(..., ge=0, description="Y coordinate")
    topology: Topology = Field(..., description="Board topology for this space")


class Panel(BaseModel):
    panel_id: str = Field(..., description="Unique panel identifier")
    name: str = Field(..., description="Panel display name")
    topology: Topology = Field(..., description="Panel topology")
    position: BoardSpace = Field(..., description="Panel position on board")
    enabled: bool = Field(default=True, description="Whether panel is enabled")


class ComponentInstance(BaseModel):
    component_id: str = Field(..., description="Unique component instance identifier")
    component_type: str = Field(..., description="Type of component")
    topology: Topology = Field(..., description="Component topology")
    position: BoardSpace = Field(..., description="Component position on board")
    hp: int = Field(default=10, ge=0, description="Component hit points")
    max_hp: int = Field(default=10, ge=0, description="Component maximum hit points")
    owner_id: str = Field(..., description="Player ID owning this component")
    hidden: bool = Field(default=False, description="Whether component is hidden from non-owners")

    @field_validator("max_hp")
    @classmethod
    def max_hp_must_be_ge_hp(cls, v: int, info) -> int:
        hp = info.data.get("hp") if hasattr(info, "data") else None
        if hp is not None and v < hp:
            raise ValueError("max_hp must be >= hp")
        return v


class TrackMeter(BaseModel):
    meter_id: str = Field(..., description="Unique track meter identifier")
    name: str = Field(..., description="Meter display name")
    topology: Topology = Field(..., description="Meter topology")
    current_value: int = Field(default=0, ge=0, description="Current meter value")
    max_value: int = Field(default=100, gt=0, description="Maximum meter value")
    step: int = Field(default=1, ge=1, description="Step increment")


class Move(BaseModel):
    move_id: str = Field(..., description="Unique move identifier")
    player_id: str = Field(..., description="Player making the move")
    topology: Topology = Field(..., description="Move topology")
    from_space: Optional[BoardSpace] = Field(None, description="Source space")
    to_space: Optional[BoardSpace] = Field(None, description="Target space")
    component_id: Optional[str] = Field(None, description="Component involved")
    metadata: dict = Field(default_factory=dict, description="Additional move metadata")


class GameState(BaseModel):
    state_id: str = Field(..., description="Unique game state identifier")
    game_type: str = Field(default="", description="Game type identifier (e.g. 'checkers', 'chess')")
    topology: Topology = Field(default=Topology.grid, description="Game board topology")
    rng_seed: int = Field(default=42, ge=0, description="Random number generator seed")
    rng_state_json: str = Field(
        default="{}",
        description="Serialized RNG state as JSON string",
    )
    players: list[PlayerInfo] = Field(
        default_factory=list,
        description="List of players in the game",
    )
    current_player_index: int = Field(
        default=0,
        ge=0,
        description="Index into players list for whose turn it is",
    )
    turn: TurnInfo = Field(..., description="Current turn information")
    winner: Optional[str] = Field(default=None, description="Player ID of the winner, or None")
    version: int = Field(default=0, ge=0, description="State version, incremented on each move")
    game_data: dict = Field(
        default_factory=dict,
        description="Game-specific state data (board positions, pieces, etc.)",
    )
    difficulty: Optional[str] = Field(
        default=None,
        description="Selected difficulty key (e.g. 'easy', 'medium'), or None for game default",
    )
    # Phase tracking — position in the config's round/turn/phase hierarchy
    current_round_index: int = Field(
        default=0, ge=0,
        description="Index into rounds list for current round",
    )
    current_turn_index: int = Field(
        default=0, ge=0,
        description="Index into turns list for current turn within the round",
    )
    current_phase_index: int = Field(
        default=0, ge=0,
        description="Index into phases list for current phase within the turn",
    )
    turn_number: int = Field(
        default=0, ge=0,
        description="Total number of completed rounds, incremented each time a full round cycle finishes",
    )
    board_spaces: dict[str, BoardSpace] = Field(
        default_factory=dict,
        description="Dictionary of board spaces keyed by position",
    )
    panels: dict[str, Panel] = Field(
        default_factory=dict,
        description="Dictionary of panels keyed by panel ID",
    )
    components: dict[str, ComponentInstance] = Field(
        default_factory=dict,
        description="Dictionary of component instances keyed by ID",
    )
    track_meters: dict[str, TrackMeter] = Field(
        default_factory=dict,
        description="Dictionary of track meters keyed by ID",
    )
    move_history: list[Move] = Field(
        default_factory=list,
        description="History of moves played in this game",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("rng_state_json")
    @classmethod
    def rng_state_json_must_be_valid_json(cls, v: str) -> str:
        import json
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"rng_state_json must be valid JSON: {e}") from e
        return v

    @field_validator("updated_at", mode="before")
    @classmethod
    def set_updated_at(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        return datetime.now(timezone.utc)

    model_config = {"arbitrary_by_alias": True, "use_enum_values": True}

    @property
    def current_player(self) -> Optional[PlayerInfo]:
        """Return the current player, or None if no players."""
        if not self.players or self.current_player_index >= len(self.players):
            return None
        return self.players[self.current_player_index]

    @property
    def current_player_id(self) -> Optional[str]:
        """Return the current player's ID, or None."""
        p = self.current_player
        return p.player_id if p else None


def to_player_view(state: GameState, viewer_id: str) -> GameState:
    """Return a player-scoped view of the game state.

    Only data visible to the viewer is kept:
    - The viewer sees their own PlayerInfo fully.
    - Other players' private data (name, score, color) is stripped.
    - Hidden components owned by others are redacted for non-owners.
    - Public (non-hidden) components are visible to all.
    """
    redacted_players = []
    for p in state.players:
        if p.player_id == viewer_id:
            redacted_players.append(p)
        else:
            redacted_players.append(PlayerInfo(
                player_id=p.player_id,
                name="",
                score=0,
                color="#000000",
            ))

    filtered_components: dict[str, ComponentInstance] = {}
    for comp_id, comp in state.components.items():
        if comp.hidden and comp.owner_id != viewer_id:
            filtered_components[comp_id] = ComponentInstance(
                component_id=comp.component_id,
                component_type=comp.component_type,
                topology=comp.topology,
                position=comp.position,
                hp=0,
                max_hp=comp.max_hp,
                owner_id=comp.owner_id,
                hidden=True,
            )
        else:
            filtered_components[comp_id] = comp

    return GameState(
        state_id=state.state_id,
        game_type=state.game_type,
        topology=state.topology,
        rng_seed=state.rng_seed,
        rng_state_json=state.rng_state_json,
        players=redacted_players,
        current_player_index=state.current_player_index,
        turn=state.turn,
        winner=state.winner,
        version=state.version,
        game_data=state.game_data,
        difficulty=state.difficulty,
        current_round_index=state.current_round_index,
        current_turn_index=state.current_turn_index,
        current_phase_index=state.current_phase_index,
        turn_number=state.turn_number,
        board_spaces=state.board_spaces,
        panels=state.panels,
        components=filtered_components,
        track_meters=state.track_meters,
        move_history=state.move_history,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )
