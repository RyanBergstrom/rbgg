"""Compare paired random-policy Lost Cities runs from both starting seats."""
from __future__ import annotations

import argparse
import json
import math

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv


def _win_rate(statistics, player_id: str) -> float:
    return statistics.winners.get(player_id, 0) / statistics.episodes


def _interval(rate: float, episodes: int) -> list[float]:
    """Return a simple 95% normal-approximation interval for a proportion."""
    margin = 1.96 * math.sqrt(max(0.0, rate * (1.0 - rate) / episodes))
    return [max(0.0, rate - margin), min(1.0, rate + margin)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--summary-directory")
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")

    def run(starting_player: str):
        summary = None
        if args.summary_directory:
            from pathlib import Path
            directory = Path(args.summary_directory)
            directory.mkdir(parents=True, exist_ok=True)
            summary = directory / f"random-{starting_player}.jsonl"
        return run_episodes(
            lambda seed: LostCitiesReferenceEnv(
                seed=seed,
                starting_player=starting_player,
            ),
            episodes=args.episodes,
            seed=args.seed,
            summary_path=summary,
        )

    player_1_start = run("player_1")
    player_2_start = run("player_2")
    result = {
        "episodes_per_seat": args.episodes,
        "seed": args.seed,
        "player_1_start": player_1_start.as_dict(),
        "player_2_start": player_2_start.as_dict(),
        "player_1_win_rate_when_starting": _win_rate(player_1_start, "player_1"),
        "player_2_win_rate_when_starting": _win_rate(player_2_start, "player_2"),
        "player_1_start_win_rate_95_percent_interval": _interval(
            _win_rate(player_1_start, "player_1"), args.episodes
        ),
        "player_2_start_win_rate_95_percent_interval": _interval(
            _win_rate(player_2_start, "player_2"), args.episodes
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
