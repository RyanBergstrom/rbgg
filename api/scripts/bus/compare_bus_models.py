"""Compare Bus PPO models head-to-head with rotated seats and varied openings.

Example: python scripts/compare_bus_models.py v2=runtime/bus-v2-2.5m.zip v5=runtime/bus-v5-diverse-1m.zip --players 3 --episodes 100
"""
from __future__ import annotations

import argparse
import collections
import json
import random
from statistics import mean

import numpy as np
from sb3_contrib import MaskablePPO

from app.games.bus.rl_adapter import BusReferenceEnv, action_id_for_move, encode_observation
from app.games.bus.rl_policies import observation_version_for_size
from app.games.bus.validator import BusValidator


class ModelPlayer:
    def __init__(self, model: MaskablePPO, deterministic: bool):
        self.model = model
        self.version = observation_version_for_size(model.observation_space.shape[0])
        self.deterministic = deterministic

    def choose(self, adapter: BusReferenceEnv, rng: random.Random) -> int:
        actor = adapter.current_player
        legal = adapter.legal_moves(actor)
        observation = encode_observation(adapter.state, actor, legal, version=self.version)
        action, _ = self.model.predict(
            np.asarray(observation["observation"], dtype=np.float32),
            action_masks=np.asarray(observation["action_mask"], dtype=bool),
            deterministic=self.deterministic,
        )
        return int(action)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="One or more LABEL=MODEL.zip values")
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--players", type=int, default=3, choices=(3, 4, 5))
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--random-setup", type=float, default=1.0,
                        help="Probability of a random legal move during setup phases.")
    parser.add_argument("--stochastic", action="store_true",
                        help="Sample model policies; default uses production deterministic actions.")
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("episodes must be positive")
    if not 0.0 <= args.random_setup <= 1.0:
        parser.error("random-setup must be between 0 and 1")

    models: dict[str, ModelPlayer] = {}
    for entry in args.models:
        label, separator, path = entry.partition("=")
        if not separator or not label or not path or label in models:
            parser.error(f"expected unique LABEL=MODEL.zip value, got {entry!r}")
        models[label] = ModelPlayer(MaskablePPO.load(path, device="cpu"), not args.stochastic)
    if len(models) < 2:
        parser.error("at least two models are required")

    labels = list(models)
    player_ids = tuple(f"player_{index + 1}" for index in range(args.players))
    scores: dict[str, list[float]] = collections.defaultdict(list)
    wins: collections.Counter[str] = collections.Counter()
    distinct_games: set[tuple[tuple[str, int], ...]] = set()
    setup_phases = {"SETUP_BUILDINGS", "SETUP_FIRST_ROUTE_SEGMENTS", "SETUP_SECOND_ROUTE_SEGMENTS"}

    for episode in range(args.episodes):
        env = BusReferenceEnv(
            seed=args.seed + episode,
            player_ids=player_ids,
            validator=BusValidator(),
        )
        observation = env.reset()
        rng = random.Random(args.seed + episode)
        assignment = {
            player_id: labels[(seat_index + episode) % len(labels)]
            for seat_index, player_id in enumerate(player_ids)
        }
        trace: list[tuple[str, int]] = []
        done = False
        info: dict = {}
        for _ in range(4000):
            actor = env.current_player
            legal = env.legal_moves(actor)
            phase = env.state["game_data"].get("current_phase")
            if phase in setup_phases and rng.random() < args.random_setup:
                action_id = action_id_for_move(rng.choice(legal))
            else:
                action_id = models[assignment[actor]].choose(env, rng)
            trace.append((actor, action_id))
            observation, _, done, info = env.step(action_id)
            if done:
                break
        else:
            raise RuntimeError(f"episode {episode} exceeded the 4000-step limit")

        distinct_games.add(tuple(trace))
        final = info.get("final_scores", {})
        for player_id, label in assignment.items():
            scores[label].append(float(final[player_id]))
        winner = info.get("winner") or info.get("ranking")
        if winner in assignment:
            wins[assignment[winner]] += 1

    result = {
        "episodes": args.episodes,
        "players": args.players,
        "total_distinct_trajectories": len(distinct_games),
        "decisions": "stochastic" if args.stochastic else "deterministic",
        "random_setup_probability": args.random_setup,
        "models": {
            label: {
                "mean_adjusted_score_per_seat": mean(scores[label]),
                "max_adjusted_score": max(scores[label]),
                "seat_count": len(scores[label]),
                "wins": wins[label],
                "win_share": wins[label] / args.episodes,
            }
            for label in labels
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
