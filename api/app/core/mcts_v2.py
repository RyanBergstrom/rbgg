"""MCTS v2 — Score-differential reward signal.

Instead of binary win/loss (1.0/0.0/0.5), returns normalized score
differential in [0, 1] from the searching player's perspective. This
gives MCTS much richer signal for scoring games like Lost Cities.

Rewards are shifted to [0, 1] via (tanh(diff/100) + 1) / 2 so the
UCT exploitation term stays balanced with the exploration constant.

Usage:
    from app.core.mcts_v2 import MCTSEngineV2, MCTSConfig
    engine = MCTSEngineV2(validator, MCTSConfig(iterations=500))
    result = engine.search(state, "player_1")
"""
from __future__ import annotations

import math
from typing import Any

from app.core.mcts import MCTSEngine, MCTSConfig, MCTSNode, MCTSResult


class MCTSEngineV2(MCTSEngine):
    """MCTS engine with score-differential rewards.

    Overrides _simulate and _backpropagate to use continuous score
    signals instead of binary win/loss.
    """

    def _simulate(self, node: MCTSNode, searching_player: str) -> tuple[float, bool]:
        """Random rollout returning normalized score differential.

        Returns (reward, finished_round) where reward is in [0, 1]:
          1.0 = searching player is way ahead
          0.5 = even
          0.0 = searching player is way behind
        """
        from app.games.lost_cities.validator import (
            _calculate_player_score,
            COLORS,
        )

        state = self._clone_state(node.state)
        current_player = self._current_player_id(state)

        for depth in range(self.config.max_depth):
            winner = self.validator.check_win(state)
            if winner is not None:
                reward = self._score_reward(state, searching_player)
                return reward, True

            if self.validator.stop_rollout(state, current_player):
                reward = self._score_reward(state, searching_player)
                return reward, True

            moves = self.validator.get_legal_moves(state, current_player)
            if not moves:
                reward = self._score_reward(state, searching_player)
                return reward, True

            move = self.rng.choice(moves)
            state = self._apply_move_to_state(state, move)
            current_player = self._current_player_id(state)

        # Depth limit reached — evaluate current position
        reward = self._score_reward(state, searching_player)
        return reward, False

    def _score_reward(self, state: dict[str, Any], searching_player: str) -> float:
        """Compute normalized score differential from searching_player's perspective.

        Returns a value in [0, 1]:
          1.0 = searching player is way ahead
          0.5 = even
          0.0 = searching player is way behind
        """
        from app.games.lost_cities.validator import _calculate_player_score

        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {})
        scores = game_data.get("scores", {})

        # Calculate current round scores from expeditions
        p1_round = _calculate_player_score(expeditions.get("player_1", {}))
        p2_round = _calculate_player_score(expeditions.get("player_2", {}))

        # Add cumulative scores from previous rounds
        p1_total = scores.get("player_1", 0) + p1_round
        p2_total = scores.get("player_2", 0) + p2_round

        # Differential from searching player's perspective
        if searching_player == "player_1":
            diff = p1_total - p2_total
        else:
            diff = p2_total - p1_total

        # Compress to [-1, 1] with tanh, then shift to [0, 1]
        # for UCT compatibility (exploitation term assumes non-negative rewards).
        raw_tanh = math.tanh(diff / 100.0)  # Range: -1.0 to 1.0
        return (raw_tanh + 1.0) / 2.0       # Range: 0.0 to 1.0

    def _backpropagate(self, node: MCTSNode, reward: float, searching_player: str) -> None:
        """Walk back to root, incrementing visits and adding perspective-aware rewards.

        For score-based rewards, we negate when it's the opponent's turn
        (a good score for the opponent is bad for the searching player).
        """
        current: MCTSNode | None = node
        while current is not None:
            current.visits += 1
            if current.player_just_moved == searching_player:
                current.wins += reward
            else:
                current.wins -= reward
            current = current.parent
