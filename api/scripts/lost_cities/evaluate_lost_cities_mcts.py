"""Evaluate MCTS through the same Lost Cities RL adapter statistics path."""
from __future__ import annotations

import argparse
import json

from app.core.mcts import MCTSConfig, MCTSEngine
from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv, action_id_for_move
from app.games.lost_cities.validator import LostCitiesValidator


def make_mcts_selector(iterations: int, strategy: str):
    def choose_mcts(adapter, observation, rng) -> int:
        del observation
        validator = adapter.validator
        config = MCTSConfig(
            iterations=iterations,
            max_depth=100,
            seed=rng.randrange(2**32),
            workers=1,
            strategy=strategy,
        )
        result = MCTSEngine(validator, config).search(
            adapter.state,
            adapter.current_player,
        )
        if result.move is None:
            raise ValueError("MCTS returned no move despite a live episode")
        return action_id_for_move(result.move)

    return choose_mcts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--strategy", choices=("legacy", "hybrid"), default="hybrid")
    parser.add_argument("--starting-player", choices=("player_1", "player_2"), default="player_1")
    parser.add_argument("--summary")
    args = parser.parse_args()
    if args.episodes < 1 or args.iterations < 1:
        parser.error("episodes and iterations must be positive")

    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(
            seed=seed,
            starting_player=args.starting_player,
            validator=LostCitiesValidator(),
        ),
        episodes=args.episodes,
        seed=args.seed,
        summary_path=args.summary,
        action_selector=make_mcts_selector(args.iterations, args.strategy),
    )
    print(json.dumps(statistics.as_dict(), indent=2, sort_keys=True))
    if args.summary:
        print(f"episode_summaries={args.summary}")


if __name__ == "__main__":
    main()
