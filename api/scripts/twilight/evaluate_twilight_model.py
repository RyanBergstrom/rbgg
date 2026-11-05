"""Evaluate a Twilight Struggle policy (saved PPO model or fixed policy) against fixed opponents.

Both factions are measured with held-out seeds (default 10_000+), so a result never mixes faction strength.
Reports finish rate, stall rate, win rate among finished games, and mean learner VP margin per matchup.
Do not promote a model on training reward alone; compare against ``rule`` here (playbook section 11).
"""
from __future__ import annotations

import argparse
import random
import time
import json
import math
from pathlib import Path

import numpy as np

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


def model_selector(path: str, deterministic: bool):
    from sb3_contrib import MaskablePPO

    # SB3 appends ".zip" to load paths; strip it if already present to avoid ".zip.zip"
    if path.endswith(".zip"):
        path = path[:-4]

    model = MaskablePPO.load(path, device="cpu")

    def _select(adapter, observation, rng):
        del adapter, rng
        action, _ = model.predict(
            np.asarray(observation["observation"], dtype=np.float32),
            action_masks=np.asarray(observation["action_mask"], dtype=bool),
            deterministic=deterministic,
        )
        return int(action)

    return _select


def play(selector, opponent: str, faction: str, seed: int, max_steps: int) -> dict:
    env = TwilightStruggleGymEnv(
        seed=seed, opponents={opponent: 1.0}, learner_faction=faction, max_episode_steps=max_steps,
    )
    env.reset(seed=seed)
    rng = random.Random(seed)
    info: dict = {}
    decisions = 0
    while True:
        if not env.action_masks().any():
            info = {**info, "stalled": True}
            break
        _, _, terminated, truncated, info = env.step(selector(env.adapter, env.adapter_observation, rng))
        decisions += 1
        if terminated or truncated:
            break
    game_data = env.adapter.game_data
    pending = env.adapter.pending
    finished = info.get("terminal_result") is not None
    terminal_result = info.get("terminal_result") or {}
    return {
        "seed": seed,
        "faction": faction,
        "opponent": opponent,
        "finished": finished,
        "stalled": bool(info.get("stalled")),
        "win": finished and info.get("winner") == info.get("learner"),
        "margin": info.get("vp_margin", 0.0),
        "decisions": decisions,
        "turn": game_data.get("turn"),
        "phase": game_data.get("current_phase"),
        "stall_stage": getattr(pending, "stage", None) if info.get("stalled") else None,
        "terminal_reason": terminal_result.get("reason"),
    }


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion, as fractions in [0, 1]."""
    if trials <= 0:
        return float("nan"), float("nan")
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    radius = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def mean_interval(values: list[float], z: float = 1.96) -> tuple[float, float]:
    """Normal-approximation 95% CI for a mean; intended for adequately sized evaluation samples."""
    if not values:
        return float("nan"), float("nan")
    mean = float(np.mean(values))
    if len(values) < 2:
        return mean, mean
    standard_error = float(np.std(values, ddof=1)) / math.sqrt(len(values))
    return mean - z * standard_error, mean + z * standard_error


def summarize(results: list[dict]) -> dict:
    completed = [row for row in results if row["finished"]]
    wins = sum(bool(row["win"]) for row in completed)
    win_low, win_high = wilson_interval(wins, len(completed))
    finish_low, finish_high = wilson_interval(len(completed), len(results))
    margins = [float(row["margin"]) for row in completed]
    margin_low, margin_high = mean_interval(margins)
    return {
        "games": len(results),
        "finished": len(completed),
        "finish_ci95": (finish_low, finish_high),
        "stalled": sum(bool(row["stalled"]) for row in results),
        "wins": wins,
        "win_rate": wins / len(completed) if completed else float("nan"),
        "win_ci95": (win_low, win_high),
        "mean_vp": float(np.mean(margins)) if margins else float("nan"),
        "vp_ci95": (margin_low, margin_high),
    }

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--model", help="Saved MaskablePPO .zip to evaluate.")
    source.add_argument("--policy", choices=sorted(FIXED_POLICIES), help="Fixed policy to evaluate instead.")
    source.add_argument("--v6", action="store_true", help=f"Evaluate C:\\\\Dev\\\\rbgg\\\\api\\\\runtime\\\\twilight\\twilight-ppo-v6.zip")
    source.add_argument("--v7", action="store_true", help=f"Evaluate C:\\\\Dev\\\\rbgg\\\\api\\\\runtime\\\\twilight\\twilight-ppo-v7.zip")
    parser.add_argument("--opponents", default="rule,random",
                        help="Comma-separated fixed opponents to face.")
    parser.add_argument("--games", type=int, default=20, help="Games per faction per opponent.")
    parser.add_argument("--seed", type=int, default=10_000, help="First held-out seed.")
    parser.add_argument("--stochastic", action="store_true",
                        help="Sample actions from the policy instead of taking the argmax.")
    parser.add_argument("--max-episode-steps", type=int, default=6000)
    parser.add_argument("--jsonl-output", help="Optional path for per-game JSONL results (appended).")
    args = parser.parse_args()

    opponents = [name.strip() for name in args.opponents.split(",") if name.strip()]
    unknown = [name for name in opponents if name not in FIXED_POLICIES]
    if unknown:
        parser.error(f"unknown opponents {unknown}; expected {sorted(FIXED_POLICIES)}")
    if args.games < 1:
        parser.error("games must be positive")
    if args.v6:
        model_path = r"C:\\Dev\\rbgg\\api\\runtime\\twilight\twilight-ppo-v6.zip"
        label = "twilight-ppo-v6"
    elif args.v7:
        model_path = r"C:\\Dev\\rbgg\\api\\runtime\\twilight\twilight-ppo-v7.zip"
        label = "twilight-ppo-v7"
    elif args.model:
        model_path = args.model
        label = args.model
    else:
        model_path = None
        label = args.policy

    selector = (
        model_selector(model_path, deterministic=not args.stochastic) if model_path else FIXED_POLICIES[args.policy]
    )

    jsonl_path = Path(args.jsonl_output) if args.jsonl_output else None
    if jsonl_path:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"evaluating {label} games/faction/opponent={args.games} seeds from {args.seed}")
    print(f"{'faction':7} {'opponent':8} {'finished':>9} {'stalled':>7} {'win% [95% CI]':>19} {'avg VP [95% CI]':>24} {'finish% [95% CI]':>20} {'sec':>6}")
    for opponent in opponents:
        for faction in ("us", "ussr"):
            started = time.time()
            results = [
                play(selector, opponent, faction, args.seed + game, args.max_episode_steps)
                for game in range(args.games)
            ]
            summary = summarize(results)
            if jsonl_path:
                with jsonl_path.open("a", encoding="utf-8") as stream:
                    for row in results:
                        stream.write(json.dumps({"policy": label, **row}, sort_keys=True) + "\n")
            win_lo, win_hi = summary["win_ci95"]
            margin_lo, margin_hi = summary["vp_ci95"]
            finish_lo, finish_hi = summary["finish_ci95"]
            print(
                f"{faction:7} {opponent:8} {summary['finished']:>4}/{summary['games']:<4} "
                f"{summary['stalled']:>7} {100*summary['win_rate']:>5.1f} [{100*win_lo:>4.1f},{100*win_hi:>4.1f}] "
                f"{summary['mean_vp']:>5.1f} [{margin_lo:>5.1f},{margin_hi:>5.1f}] "
                f"{100*summary['finished']/summary['games']:>5.1f} [{100*finish_lo:>4.1f},{100*finish_hi:>4.1f}] "
                f"{time.time() - started:>6.1f}"
            )


if __name__ == "__main__":
    main()
