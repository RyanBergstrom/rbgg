"""Compare random, heuristic, and MCTS policies through one RL pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv
from app.games.lost_cities.validator import LostCitiesValidator
from evaluate_lost_cities_heuristic import choose_heuristic
from evaluate_lost_cities_mcts import make_mcts_selector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--mcts-iterations", type=int, default=10)
    parser.add_argument("--starting-player", choices=("player_1", "player_2"), default="player_1")
    parser.add_argument("--summary-directory")
    args = parser.parse_args()
    if args.episodes < 1 or args.mcts_iterations < 1:
        parser.error("episodes and mcts-iterations must be positive")

    policies = {
        "random": None,
        "heuristic": choose_heuristic,
        "mcts_hybrid": make_mcts_selector(args.mcts_iterations, "hybrid"),
    }
    result = {}
    for name, selector in policies.items():
        summary_path = None
        if args.summary_directory:
            directory = Path(args.summary_directory)
            directory.mkdir(parents=True, exist_ok=True)
            summary_path = directory / f"{name}.jsonl"
        result[name] = run_episodes(
            lambda seed: LostCitiesReferenceEnv(
                seed=seed,
                starting_player=args.starting_player,
                validator=LostCitiesValidator(),
            ),
            episodes=args.episodes,
            seed=args.seed,
            summary_path=summary_path,
            action_selector=selector,
        ).as_dict()

    print(json.dumps({
        "episodes_per_policy": args.episodes,
        "seed": args.seed,
        "starting_player": args.starting_player,
        "mcts_iterations": args.mcts_iterations,
        "policies": result,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
