"""Evaluate a masked PPO Lost Cities model through the shared statistics runner.

``--opponent self`` plays the model in both seats. Any other opponent plays the
model in ``--model-seat`` against a fixed policy, which is the meaningful
strength measurement (fixed baselines: never_play = 0 points, rule ~ +46).
"""
from __future__ import annotations

import argparse
import json

from sb3_contrib import MaskablePPO

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv
from app.games.lost_cities.rl_policies import (
    FIXED_POLICIES,
    make_model_selector,
    make_seat_selector,
    observation_version_for_size,
)
from app.games.lost_cities.validator import LostCitiesValidator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--starting-player", choices=("player_1", "player_2"), default="player_1")
    parser.add_argument("--opponent", choices=("self", *sorted(FIXED_POLICIES)), default="self")
    parser.add_argument("--model-seat", choices=("player_1", "player_2"), default="player_1")
    parser.add_argument("--summary")
    parser.add_argument("--max-steps", type=int)
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("episodes must be positive")

    model = MaskablePPO.load(args.model, device="cpu")
    version = observation_version_for_size(model.observation_space.shape[0])
    selector = make_model_selector(model)
    if args.opponent != "self":
        selector = make_seat_selector(args.model_seat, selector, FIXED_POLICIES[args.opponent])
    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(
            seed=seed,
            starting_player=args.starting_player,
            validator=LostCitiesValidator(),
            observation_version=version,
        ),
        episodes=args.episodes,
        seed=args.seed,
        summary_path=args.summary,
        action_selector=selector,
        max_steps_per_episode=args.max_steps,
    )
    result = statistics.as_dict()
    result["observation_version"] = version
    if args.opponent != "self":
        result["opponent"] = args.opponent
        result["model_seat"] = args.model_seat
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.summary:
        print(f"episode_summaries={args.summary}")


if __name__ == "__main__":
    main()
