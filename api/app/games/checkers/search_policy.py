"""Checkers evaluation policy for the generic search engines."""
from __future__ import annotations

import math
from typing import Any

from app.core.search_policy import ValidatorSearchPolicy
from app.games.checkers.validator import BLACK, BLACK_KING, RED, RED_KING


class CheckersSearchPolicy(ValidatorSearchPolicy):
    """Material-based horizon evaluation for Checkers."""

    def horizon_value(self, state: dict[str, Any], root_player_id: str) -> float:
        board = state.get("game_data", {}).get("board")
        if board is None:
            return 0.5
        own = opponent = 0
        own_pieces = (RED, RED_KING) if root_player_id == "player_1" else (BLACK, BLACK_KING)
        for row in board:
            for cell in row:
                if cell in own_pieces:
                    own += 2 if cell in (RED_KING, BLACK_KING) else 1
                elif cell in (RED, RED_KING, BLACK, BLACK_KING):
                    opponent += 2 if cell in (RED_KING, BLACK_KING) else 1
        return (math.tanh((own - opponent) / 8.0) + 1.0) / 2.0
