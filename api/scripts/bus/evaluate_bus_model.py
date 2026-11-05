"""Evaluate a masked PPO Bus model through the shared statistics runner.

``--opponent self`` plays the model in every seat. Any other opponent plays
the model in ``--model-seat`` against a fixed policy for every other seat,
which is the meaningful strength measurement (fixed baselines: ``null`` = 0
adjusted score/game, ``rule`` beats both -- see
``documentation/Bus/bus-rl-analysis.md`` for the recorded baseline table).
"""
from __future__ import annotations

import argparse
import json

from sb3_contrib import MaskablePPO

from app.core.rl_runner import run_episodes
from app.games.bus.rl_adapter import BusReferenceEnv
from app.games.bus.rl_policies import (
    FIXED_POLICIES,
    make_model_selector,
    make_seat_selector,
    observation_version_for_size,
)
from app.games.bus.validator import BusValidator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--players", type=int, default=3, choices=(3, 4, 5))
    parser.add_argument("--opponent", choices=("self", *sorted(FIXED_POLICIES)), default="rule")
    parser.add_argument("--model-seat", default="player_1")
    parser.add_argument("--stochastic", action="store_true",
                        help="Sample from the masked model policy instead of greedy actions.")
    parser.add_argument("--random-setup", type=float, default=0.0, metavar="PROBABILITY",
                        help="During setup, choose a uniformly random legal move with this probability (0-1).")
    parser.add_argument("--summary")
    parser.add_argument("--max-steps", type=int, default=3000)
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("episodes must be positive")
    if not 0.0 <= args.random_setup <= 1.0:
        parser.error("random-setup must be between 0 and 1")
    player_ids = tuple(f"player_{i + 1}" for i in range(args.players))
    if args.model_seat not in player_ids:
        parser.error(f"model-seat must be one of {player_ids}")

    model = MaskablePPO.load(args.model, device="cpu")
    version = observation_version_for_size(model.observation_space.shape[0])
    selector = make_model_selector(model, deterministic=not args.stochastic)
    if args.opponent != "self":
        selector = make_seat_selector(args.model_seat, selector, FIXED_POLICIES[args.opponent])
    if args.random_setup:
        setup_phases = {"SETUP_BUILDINGS", "SETUP_FIRST_ROUTE_SEGMENTS", "SETUP_SECOND_ROUTE_SEGMENTS"}
        base_selector = selector

        def selector(adapter, observation, rng):
            if adapter.state["game_data"].get("current_phase") in setup_phases and rng.random() < args.random_setup:
                enabled = [index for index, flag in enumerate(observation["action_mask"]) if flag]
                return rng.choice(enabled)
            return base_selector(adapter, observation, rng)
    statistics = run_episodes(
        lambda seed: BusReferenceEnv(
            seed=seed,
            player_ids=player_ids,
            validator=BusValidator(),
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
    result["model_decisions"] = "stochastic" if args.stochastic else "deterministic"
    result["random_setup_probability"] = args.random_setup
    if args.opponent != "self":
        result["opponent"] = args.opponent
        result["model_seat"] = args.model_seat
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
