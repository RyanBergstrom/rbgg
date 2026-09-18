from __future__ import annotations

from typing import Any

from app.core.legal_move_interface import (
    IllegalMoveError,
    ValidatorConsistencyError,
    LegalMoveValidator,
)
from app.core.rng import create_rng, serialize_rng, serialize_rng_state


class MovePipeline:
    """Defense-in-depth move validation and execution pipeline.

    The pipeline enforces a strict check order:
    1. Payload schema validation
    2. Legal-move set check (via LegalMoveValidator)
    3. Version/concurrency check
    4. Apply move + check win

    Each step short-circuits on failure.
    """

    def __init__(self, validator: LegalMoveValidator | None = None) -> None:
        self.validator = validator or _DefaultValidator()

    def submit_move(
        self,
        state: dict[str, Any],
        move: dict[str, Any],
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Submit a move through the pipeline.

        Returns a dict with ``move_id``, ``status``, ``new_state``, and ``winner``.

        Raises:
            IllegalMoveError: If the move fails payload or legal-set checks.
            ValueError: If a version conflict is detected.
        """
        # 1. Payload schema validation
        if not isinstance(move, dict):
            raise IllegalMoveError("move payload must be a mapping")

        move_id = move.get("move_id")
        if not move_id:
            raise IllegalMoveError("move payload must contain a non-empty move_id")

        # 2. Legal-move set check
        if not self.validator.validate_move(state, move):
            raise IllegalMoveError("move is not in the legal move set")

        # 3. Version conflict check
        if expected_version is not None:
            current_version = state.get("version", 0)
            if expected_version != current_version:
                raise ValueError(
                    f"version conflict: expected {expected_version}, got {current_version}"
                )

        # 4. Apply move
        new_state = self.validator.apply_move(state, move)

        # Carry forward players so check_win can evaluate the result
        if "players" not in new_state:
            new_state["players"] = state.get("players", [])
        if "current_player_index" not in new_state:
            new_state["current_player_index"] = state.get("current_player_index", 0)

        # 5. Advance RNG (deterministic replay: same seed + moves = same state)
        rng_seed = new_state.get("rng_seed", 42)
        rng_state_json = new_state.get("rng_state_json", "{}")
        rng = create_rng(rng_seed, rng_state_json)
        rng.random()  # advance once per move
        new_state["rng_state_json"] = serialize_rng(rng)

        # 6. Check win
        winner = self.validator.check_win(new_state)

        return {
            "move_id": move_id,
            "status": "accepted",
            "new_state": new_state,
            "winner": winner,
        }

    def get_legal_moves_for_player(
        self, state: dict[str, Any], player_id: str
    ) -> list[dict[str, Any]]:
        """Return the list of legal moves for a given player."""
        return self.validator.get_legal_moves(state, player_id)

    def get_ai_move(
        self, state: dict[str, Any], candidate_moves: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Return an AI-chosen move from the candidate list."""
        return self.validator.recommend_ai_move(state, candidate_moves)


class _DefaultValidator(LegalMoveValidator):
    """Minimal validator used when none is supplied. Accepts everything."""

    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        return True

    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        return []

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        return state

    def check_win(self, state: dict[str, Any]) -> str | None:
        return None


# ── Phase-aware game engine ────────────────────────────────────────────

class GameEngine:
    """Phase-aware game engine that wraps MovePipeline with config-driven
    round/turn/phase tracking.

    Lifecycle:
    1. ``start_game`` — initializes state at round 0, turn 0, phase 0
    2. ``get_phase_info`` — returns current phase config to the frontend
    3. ``submit_move`` — validates + applies move, auto-advances phase if needed
    4. ``confirm_turn`` — advances past a confirm-required phase to next player
    """

    def __init__(self, game_id: str, validator: LegalMoveValidator) -> None:
        from app.core.config_loader import load_game_config
        self.game_id = game_id
        self.validator = validator
        self.config = load_game_config(game_id)
        self.pipeline = MovePipeline(validator)

    # ── Config lookups ─────────────────────────────────────────────────

    def _get_round(self, round_index: int):
        """Return the RoundConfig at round_index, or None."""
        if round_index < len(self.config.rounds):
            return self.config.rounds[round_index]
        return None

    def _get_turn(self, round_index: int, turn_index: int):
        """Return the TurnConfig at (round, turn), or None."""
        rnd = self._get_round(round_index)
        if rnd is None:
            return None
        if turn_index < len(rnd.turns):
            return rnd.turns[turn_index]
        return None

    def _get_phase(self, round_index: int, turn_index: int, phase_index: int):
        """Return the PhaseConfig at (round, turn, phase), or None."""
        turn = self._get_turn(round_index, turn_index)
        if turn is None:
            return None
        if phase_index < len(turn.phases):
            return turn.phases[phase_index]
        return None

    # ── Phase info (for frontend) ──────────────────────────────────────

    def get_phase_info(self, state) -> dict[str, Any]:
        """Return the current phase info the frontend needs to render UI.

        Returns:
            {
                "phase_name": "Player_Turn",
                "phase_text": "Make your move",
                "confirm_required": false,
                "confirm_name": "Confirm",
                "confirm_description": "End your turn",
                "round_name": "Main Game",
                "turn_name": "Player Turn",
            }
        """
        phase = self._get_phase(
            state.current_round_index,
            state.current_turn_index,
            state.current_phase_index,
        )

        # Fallback: games that manage their own phase tracking store
        # current_phase as a string in game_data.  Look it up in config.
        if phase is None:
            game_data = getattr(state, "game_data", {})
            phase_name = game_data.get("current_phase", "")
            if phase_name:
                phase = self._find_phase_by_name(phase_name)

        if phase is None:
            return {
                "phase_name": "",
                "phase_text": "",
                "confirm_required": False,
                "confirm_name": "Confirm",
                "confirm_description": "",
                "round_name": "",
                "turn_name": "",
            }

        confirm = phase.confirm
        rnd = self._get_round(state.current_round_index)
        turn = self._get_turn(state.current_round_index, state.current_turn_index)

        return {
            "phase_name": phase.name,
            "phase_text": phase.text,
            "confirm_required": confirm.required if confirm else False,
            "confirm_name": confirm.name if confirm else "Confirm",
            "confirm_description": confirm.description if confirm else "",
            "round_name": rnd.name if rnd else "",
            "turn_name": turn.name if turn else "",
        }

    def _find_phase_by_name(self, phase_name: str):
        """Find a PhaseConfig by name across all rounds/turns."""
        for rnd in self.config.rounds:
            for turn in rnd.turns:
                for p in turn.phases:
                    if p.name == phase_name:
                        return p
        return None

    def should_show_confirm(self, state) -> bool:
        """Check if the current phase requires a confirm button."""
        phase = self._get_phase(
            state.current_round_index,
            state.current_turn_index,
            state.current_phase_index,
        )
        if phase is None or phase.confirm is None:
            return False
        return phase.confirm.required

    # ── Phase advancement ──────────────────────────────────────────────

    def advance_phase(self, state) -> None:
        """Advance to the next phase. Handles turn and round transitions.

        Mutates state in place:
        - If more phases in current turn → increment current_phase_index
        - If no more phases → reset phase to 0, advance to next player
        - If no more turns in round → reset turn+phase to 0, next round (if any)
        """
        turn = self._get_turn(state.current_round_index, state.current_turn_index)

        if turn is None:
            # Past the last round — loop back to round 0 and advance player
            state.current_round_index = 0
            state.current_turn_index = 0
            state.current_phase_index = 0
            state.turn_number += 1
            if state.players:
                state.current_player_index = (
                    (state.current_player_index + 1) % len(state.players)
                )
                current_player = state.players[state.current_player_index]
                from app.core.game_state import TurnInfo, Topology
                state.turn = TurnInfo(
                    turn_id=f"t{state.version + 1}",
                    player_id=current_player.player_id,
                    topology=Topology.grid,
                )
            return

        if state.current_phase_index + 1 < len(turn.phases):
            # More phases in this turn
            state.current_phase_index += 1
        else:
            # Turn complete — check if round is also complete before resetting
            rnd = self._get_round(state.current_round_index)
            if rnd and state.current_turn_index + 1 >= len(rnd.turns):
                # All turns in round done — advance round and increment turn_number
                state.current_round_index += 1
                state.turn_number += 1

            state.current_phase_index = 0
            state.current_turn_index = 0

            # Advance to next player
            if state.players:
                state.current_player_index = (
                    (state.current_player_index + 1) % len(state.players)
                )

            # Update turn info
            if state.players:
                current_player = state.players[state.current_player_index]
                from app.core.game_state import TurnInfo, Topology
                state.turn = TurnInfo(
                    turn_id=f"t{state.version + 1}",
                    player_id=current_player.player_id,
                    topology=Topology.grid,
                )

    # ── Move submission ────────────────────────────────────────────────

    def _build_state_dict(self, state) -> dict[str, Any]:
        """Build the state dict the validator expects."""
        return {
            "players": [p.__dict__ for p in state.players],
            "current_player_index": state.current_player_index,
            "game_data": state.game_data,
            "version": state.version,
        }

    def submit_move(self, state, move: dict[str, Any], expected_version: int | None = None) -> dict[str, Any]:
        """Submit a move through the pipeline with phase tracking.

        Returns:
            {
                "move_id": ...,
                "status": "accepted" | "confirm_required",
                "new_state": {...},
                "winner": ...,
                "phase_info": {...},
            }
        """
        state_dict = self._build_state_dict(state)
        result = self.pipeline.submit_move(state_dict, move, expected_version)

        # Apply results back to GameState
        state.game_data = result["new_state"].get("game_data", state.game_data)

        # Sync engine's current_player_index with game_data.current_player
        game_data_player = state.game_data.get("current_player")
        if game_data_player and state.players:
            for i, p in enumerate(state.players):
                if p.player_id == game_data_player:
                    state.current_player_index = i
                    break

        state.version += 1
        winner = result.get("winner")

        if winner:
            state.winner = winner
            return {
                "move_id": result["move_id"],
                "status": "accepted",
                "new_state": result["new_state"],
                "winner": winner,
                "phase_info": self.get_phase_info(state),
            }

        # Check if multi-jump continuation is required
        must_jump = state.game_data.get("must_jump_from") if hasattr(state, "game_data") else None
        if must_jump:
            return {
                "move_id": result["move_id"],
                "status": "accepted",
                "new_state": result["new_state"],
                "winner": None,
                "phase_info": self.get_phase_info(state),
            }

        # No more legal moves — check if current phase requires confirm
        if self.should_show_confirm(state):
            return {
                "move_id": result["move_id"],
                "status": "confirm_required",
                "new_state": result["new_state"],
                "winner": None,
                "phase_info": self.get_phase_info(state),
            }

        # Auto-advance to next phase
        self.advance_phase(state)
        return {
            "move_id": result["move_id"],
            "status": "accepted",
            "new_state": result["new_state"],
            "winner": None,
            "phase_info": self.get_phase_info(state),
        }

    # ── Confirm handling ───────────────────────────────────────────────

    def confirm_turn(self, state) -> dict[str, Any]:
        """Handle confirm action — advance past confirm phase to next player."""
        if not self.should_show_confirm(state):
            return {
                "status": "no_confirm_needed",
                "phase_info": self.get_phase_info(state),
            }

        self.advance_phase(state)
        return {
            "status": "turn_complete",
            "phase_info": self.get_phase_info(state),
        }

    # ── Legal moves ────────────────────────────────────────────────────

    def get_legal_moves(self, state, player_id: str) -> list[dict[str, Any]]:
        """Return legal moves for the given player."""
        state_dict = self._build_state_dict(state)
        return self.validator.get_legal_moves(state_dict, player_id)

    # ── Screen state ────────────────────────────────────────────────────

    def build_screen_state(
        self, state, legal_moves: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Build the complete screen state JSON from config + game state.

        Returns a dict with:
            panels: list of {id, name, components: [{id, name, shape, color, ...}]}
            phase: current phase info dict
            legal_moves: list of legal move dicts
            current_player: current player id
            winner: winner player id or None
            game_data: serialized game-specific data (from validator.serialize_for_screen)
        """
        # Get game-specific serialized data from validator
        raw_game_data = getattr(state, "game_data", {})
        try:
            serialized = self.validator.serialize_for_screen(raw_game_data)
        except Exception:
            serialized = raw_game_data

        # Determine current_player: prefer game_data's own tracking over engine index
        current_player = None
        if serialized.get("current_player"):
            current_player = serialized["current_player"]
        elif state.players and hasattr(state, "current_player_index"):
            idx = state.current_player_index
            if 0 <= idx < len(state.players):
                current_player = state.players[idx].player_id

        panels: list[dict[str, Any]] = []
        for panel_id, panel_config in self.config.panels.items():
            components: list[dict[str, Any]] = []
            for comp_name, comp_config in panel_config.components.items():
                comp: dict[str, Any] = {
                    "id": comp_name,
                    "name": comp_config.name,
                    "shape": comp_config.shape,
                    "z_index": comp_config.z_index,
                    "clickable": comp_config.clickable,
                }
                if comp_config.color is not None:
                    comp["color"] = comp_config.color
                if comp_config.background_image is not None:
                    comp["background_image"] = comp_config.background_image
                if comp_config.grid is not None:
                    grid_dict = comp_config.grid.to_dict()
                    # If serialized data has cells for this grid, populate them
                    if "cells" in serialized:
                        grid_dict["cells"] = serialized["cells"]
                    comp["grid"] = grid_dict
                if comp_config.hover_text is not None:
                    comp["hover_text"] = comp_config.hover_text
                if comp_config.stackable:
                    comp["stackable"] = True
                if comp_config.stack_name is not None:
                    comp["stack_name"] = comp_config.stack_name
                if comp_config.rotate is not None:
                    comp["rotate"] = comp_config.rotate
                components.append(comp)
            panels.append({
                "id": panel_id,
                "name": panel_config.name,
                "components": components,
            })

        return {
            "panels": panels,
            "phase": self.get_phase_info(state),
            "legal_moves": legal_moves or [],
            "current_player": current_player,
            "winner": getattr(state, "winner", None),
            "game_data": serialized,
            "config": {
                "hover_zoom": self.config.hover_zoom,
            },
        }
