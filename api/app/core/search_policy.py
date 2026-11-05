"""Search policy contracts and the generic validator adapter."""
from __future__ import annotations

import copy
import math
from typing import Any, Protocol

from app.core.legal_move_interface import LegalMoveValidator


class SearchPolicy(Protocol):
    """Game policy surface consumed by the generic MCTS engines."""

    def legal_moves(self, state: dict[str, Any], actor_id: str) -> list[dict[str, Any]]: ...
    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]: ...
    def current_player(self, state: dict[str, Any]) -> str: ...
    def opponent_player(self, state: dict[str, Any], player_id: str) -> str | None: ...
    def is_terminal(self, state: dict[str, Any]) -> bool: ...
    def stop_rollout(self, state: dict[str, Any], actor_id: str) -> bool: ...
    def filter_moves(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]], turn: int) -> list[dict[str, Any]]: ...
    def prior_moves(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]], turn: int) -> dict[str, float]: ...
    def expansion_weights(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]]) -> dict[str, float]: ...
    def score_moves(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]]) -> dict[str, float]: ...
    def terminal_reward(self, state: dict[str, Any], root_player_id: str) -> float: ...
    def score_reward(self, state: dict[str, Any], searching_player: str, winner: str | None = None) -> float: ...
    def one_ply_value(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float: ...
    def horizon_value(self, state: dict[str, Any], root_player_id: str) -> float: ...
    def is_dominated_action(self, state: dict[str, Any], move: dict[str, Any], root_player_id: str) -> bool: ...
    def adjust_action_values(self, state: dict[str, Any], moves: list[dict[str, Any]], values: dict[str, float], root_player_id: str) -> dict[str, float]: ...
    def optimistic_action_bound(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float: ...
    def discard_relief(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float: ...


class ValidatorSearchPolicy:
    """Generic adapter for validator mechanics and legacy fallback evaluation."""

    def __init__(self, validator: LegalMoveValidator) -> None:
        self.validator = validator

    def legal_moves(self, state: dict[str, Any], actor_id: str) -> list[dict[str, Any]]:
        return self.validator.get_legal_moves(state, actor_id)

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        new_state = copy.deepcopy(state)
        result = self.validator.apply_move(new_state, move)
        if isinstance(result, dict):
            for key, value in result.items():
                new_state[key] = copy.deepcopy(value)
        new_state["game_data"] = result.get("game_data", new_state.get("game_data", {}))
        new_state.setdefault("players", copy.deepcopy(state.get("players", [])))
        new_state.setdefault("current_player_index", state.get("current_player_index", 0))
        game_data = new_state.get("game_data", {})
        current_player = game_data.get("current_player")
        if current_player:
            for index, player in enumerate(new_state["players"]):
                if player.get("player_id") == current_player:
                    new_state["current_player_index"] = index
                    break
        elif not game_data.get("must_jump_from") and new_state["players"]:
            new_state["current_player_index"] = (state.get("current_player_index", 0) + 1) % len(new_state["players"])
        return new_state

    def current_player(self, state: dict[str, Any]) -> str:
        game_data = state.get("game_data", {})
        current = game_data.get("current_player")
        if current:
            return current
        players = state.get("players", [])
        index = state.get("current_player_index", 0)
        return players[index].get("player_id", "") if 0 <= index < len(players) else ""

    def opponent_player(self, state: dict[str, Any], player_id: str) -> str | None:
        for player in state.get("players", []):
            candidate = player.get("player_id")
            if candidate and candidate != player_id:
                return candidate
        return None

    def is_terminal(self, state: dict[str, Any]) -> bool:
        return self.validator.check_win(state) is not None or bool(state.get("game_data", {}).get("game_over"))

    def stop_rollout(self, state: dict[str, Any], actor_id: str) -> bool:
        return self.validator.stop_rollout(state, actor_id)

    def filter_moves(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]], turn: int) -> list[dict[str, Any]]:
        return self.validator.filter_moves(state, actor_id, moves, turn)

    def prior_moves(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]], turn: int) -> dict[str, float]:
        return self.validator.prior_moves(state, actor_id, moves, turn)

    def expansion_weights(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]]) -> dict[str, float]:
        return self.validator.expansion_weights(state, actor_id, moves)

    def score_moves(self, state: dict[str, Any], actor_id: str, moves: list[dict[str, Any]]) -> dict[str, float]:
        return self.validator.score_moves(state, actor_id, moves)

    def terminal_reward(self, state: dict[str, Any], root_player_id: str) -> float:
        winner = self.validator.check_win(state)
        if winner == "draw" or winner is None:
            return 0.5
        return 1.0 if winner == root_player_id else 0.0

    def score_reward(self, state: dict[str, Any], searching_player: str, winner: str | None = None) -> float:
        callback = getattr(self.validator, "score_reward", None)
        if callback is not None:
            return float(callback(state, searching_player, winner))
        return self.terminal_reward(state, searching_player) if winner is not None else 0.5

    def one_ply_value(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float:
        return 0.5

    def horizon_value(self, state: dict[str, Any], root_player_id: str) -> float:
        return 0.5

    def is_dominated_action(self, state: dict[str, Any], move: dict[str, Any], root_player_id: str) -> bool:
        return False

    def adjust_action_values(self, state: dict[str, Any], moves: list[dict[str, Any]], values: dict[str, float], root_player_id: str) -> dict[str, float]:
        return values

    def optimistic_action_bound(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float:
        return 1.0

    def discard_relief(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float:
        return 0.0


def policy_for_validator(validator: LegalMoveValidator) -> SearchPolicy:
    """Ask a validator for its game policy, falling back to the adapter."""
    factory = getattr(validator, "create_search_policy", None)
    if factory is not None:
        return factory(validator)
    return ValidatorSearchPolicy(validator)
