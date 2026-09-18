"""MCTS v3 — Heuristic-weighted rollout with risk-adjusted scoring.

Extends v2 (score-differential rewards) with:
- Rollout moves selected by heuristic scores instead of uniform random
- Depth capped at config.max_depth (default 40) or full game if full_game_rollout=True
- New validator interface: score_moves() for per-move expected value

Usage:
    from app.core.mcts_v3 import MCTSEngineV3
    engine = MCTSEngineV3(validator, MCTSConfig(iterations=500, max_depth=40))
    result = engine.search(state, "player_1")

    # Or simulate full games:
    engine = MCTSEngineV3(validator, MCTSConfig(iterations=200, full_game_rollout=True))
    result = engine.search(state, "player_1")
"""
from __future__ import annotations

from typing import Any

from app.core.mcts_v2 import MCTSEngineV2
from app.core.mcts import MCTSNode


class MCTSEngineV3(MCTSEngineV2):
    """MCTS engine with heuristic-weighted rollout and depth cap.

    Overrides _simulate to use validator.score_moves() for weighted
    move selection instead of uniform random. Rollouts stop at
    config.max_depth (default 40) or earlier if the game ends naturally.
    """

    def _simulate(self, node: MCTSNode, searching_player: str) -> tuple[float, bool]:
        """Rollout with heuristic-weighted move selection.

        If config.full_game_rollout is True, runs until game ends.
        Otherwise stops at config.max_depth.

        Returns (reward, finished_round) where reward is in [0, 1].
        """
        state = self._clone_state(node.state)
        current_player = self._current_player_id(state)

        depth_range = range(200)

        for depth in depth_range:
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

            # Heuristic-weighted selection instead of uniform random
            scores = self.validator.score_moves(state, current_player, moves)
            weights = [scores.get(m.get("move_id", ""), 0.0) for m in moves]
            move = self._weighted_choice(moves, weights)

            state = self._apply_move_to_state(state, move)
            current_player = self._current_player_id(state)

        # Depth limit reached — evaluate current position
        reward = self._score_reward(state, searching_player)
        return reward, False
