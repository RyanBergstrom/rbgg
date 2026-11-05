"""Evaluate the existing Lost Cities heuristic through the RL adapter."""
from __future__ import annotations

import argparse
import json

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import (
    LostCitiesReferenceEnv,
    action_id_for_move,
)
from app.games.lost_cities.validator import LostCitiesValidator


def choose_heuristic(adapter, observation, rng) -> int:
    """Use the existing validator heuristic, returning an adapter action ID."""
    del observation, rng
    legal_moves = adapter.legal_moves(adapter.current_player)
    validator = adapter.validator
    move = validator.recommend_ai_move(adapter.state, legal_moves)
    if move is None:
        raise ValueError("heuristic returned no move despite legal moves")
    return action_id_for_move(move)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--starting-player", choices=("player_1", "player_2"), default="player_1")
    parser.add_argument("--summary")
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")

    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(
            seed=seed,
            starting_player=args.starting_player,
            validator=LostCitiesValidator(),
        ),
        episodes=args.episodes,
        seed=args.seed,
        summary_path=args.summary,
        action_selector=choose_heuristic,
    )
    print(json.dumps(statistics.as_dict(), indent=2, sort_keys=True))
    if args.summary:
        print(f"episode_summaries={args.summary}")


if __name__ == "__main__":
    main()
