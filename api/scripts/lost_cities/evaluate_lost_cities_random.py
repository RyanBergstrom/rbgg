"""Run a random-policy Lost Cities baseline and report its outcomes."""
from __future__ import annotations

import argparse
import json

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument(
        "--starting-player",
        choices=("player_1", "player_2"),
        default="player_1",
    )
    parser.add_argument(
        "--summary",
        help="Optional JSONL path for one compact record per episode.",
    )
    parser.add_argument(
        "--flush-summaries",
        action="store_true",
        help="Flush the JSONL file after each episode for crash resilience.",
    )
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")

    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(
            seed=seed,
            starting_player=args.starting_player,
        ),
        episodes=args.episodes,
        seed=args.seed,
        summary_path=args.summary,
        flush_summaries=args.flush_summaries,
    )
    print(json.dumps(statistics.as_dict(), indent=2, sort_keys=True))
    if args.summary:
        print(f"episode_summaries={args.summary}")


if __name__ == "__main__":
    main()
