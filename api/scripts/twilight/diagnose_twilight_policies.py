"""Baseline table for Twilight Struggle policies (playbook baseline gate).

Each fixed policy plays the learner seat against each fixed opponent, alternating factions.
Reports finish rate, learner win rate among finished games, mean VP margin, and steps.
"""
from __future__ import annotations

import argparse
import random
import time

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


def play(policy: str, opponent: str, seed: int, faction: str) -> dict:
    env = TwilightStruggleGymEnv(seed=seed, opponents={opponent: 1.0}, learner_faction=faction)
    obs, _ = env.reset(seed=seed)
    rng = random.Random(seed)
    selector = FIXED_POLICIES[policy]
    info: dict = {}
    for _ in range(env.max_episode_steps + 5):
        observation = env.adapter.observe(env.learner)
        action = selector(env.adapter, observation, rng)
        obs, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
    return {"terminated": bool(info.get("terminal_result")), "info": info,
            "steps": env.steps, "stalled": bool(info.get("stalled")), "faction": faction}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=8)
    args = parser.parse_args()
    print(f"{'policy':8} {'opponent':8} {'finished':>8} {'wins':>5} {'avg_vp':>7} {'stalled':>7} {'sec':>6}")
    for policy in FIXED_POLICIES:
        for opponent in FIXED_POLICIES:
            started = time.time()
            results = [play(policy, opponent, seed, "us" if seed % 2 == 0 else "ussr") for seed in range(args.games)]
            done = [r for r in results if r["terminated"]]
            wins = sum(1 for r in done if r["info"].get("winner") == r["info"]["learner"])
            avg = sum(r["info"]["vp_margin"] for r in done) / max(1, len(done))
            stalled = sum(1 for r in results if r["stalled"])
            print(f"{policy:8} {opponent:8} {len(done):>3}/{len(results):<4} {wins:>5} {avg:>7.1f} {stalled:>7} {time.time() - started:>6.1f}")


if __name__ == "__main__":
    main()
