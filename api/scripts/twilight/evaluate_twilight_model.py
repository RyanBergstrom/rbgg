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


def resolve_model_path(path: str | Path) -> str:
    """Resolve a model path considering repo root, api directory, and runtime folders."""
    candidate = Path(path)
    if candidate.is_file():
        return str(candidate.resolve())
    if candidate.with_suffix(".zip").is_file():
        return str(candidate.with_suffix(".zip").resolve())
    repo_root = Path(__file__).resolve().parents[3]
    api_dir = repo_root / "api"
    path_str = str(path)
    candidates = [
        Path.cwd() / path,
        api_dir / "runtime" / "twilight" / path,
        api_dir / "runtime" / path,
        repo_root / "runtime" / "twilight" / path,
        repo_root / "runtime" / path,
        repo_root / path,
        api_dir / path,
    ]
    norm = path_str.replace("\\", "/")
    if norm.startswith("api/"):
        candidates.append(repo_root / norm)
        candidates.append(repo_root / norm[4:])
    for c in candidates:
        if c.is_file():
            return str(c.resolve())
        if c.with_suffix(".zip").is_file():
            return str(c.with_suffix(".zip").resolve())
    return str(path)


def model_selector(path: str, deterministic: bool):
    from sb3_contrib import MaskablePPO

    resolved = resolve_model_path(path)
    # SB3 appends ".zip" to load paths; strip it if already present to avoid ".zip.zip"
    if resolved.endswith(".zip"):
        load_path = resolved[:-4]
    else:
        load_path = resolved

    model = MaskablePPO.load(load_path, device="cpu")

    def _select(adapter, observation, rng):
        del adapter, rng
        action, _ = model.predict(
            np.asarray(observation["observation"], dtype=np.float32),
            action_masks=np.asarray(observation["action_mask"], dtype=bool),
            deterministic=deterministic,
        )
        return int(action)

    return _select


def play(selector, opponent: str, faction: str, seed: int, max_steps: int, schema_version: int = 1) -> dict:
    env = TwilightStruggleGymEnv(
        seed=seed, opponents={opponent: 1.0}, learner_faction=faction, max_episode_steps=max_steps,
        schema_version=schema_version,
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
    winner = info.get("winner")
    learner = info.get("learner")
    is_draw = finished and (winner == "draw" or terminal_result.get("winner") == "draw")
    is_win = finished and (winner == learner) and not is_draw
    is_loss = finished and not is_win and not is_draw
    return {
        "seed": seed,
        "faction": faction,
        "opponent": opponent,
        "finished": finished,
        "stalled": bool(info.get("stalled")),
        "truncated": bool(truncated and not finished),
        "win": is_win,
        "loss": is_loss,
        "draw": is_draw,
        "winner": winner,
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
    total_games = len(results)
    completed = [row for row in results if row["finished"]]
    wins = sum(bool(row["win"]) for row in completed)
    draws = sum(bool(row.get("draw")) for row in completed)
    losses = sum(bool(row.get("loss", not row["win"] and not row.get("draw"))) for row in completed)
    stalls = sum(bool(row.get("stalled")) for row in results)
    truncations = sum(bool(row.get("truncated")) for row in results)

    win_low, win_high = wilson_interval(wins, len(completed))
    win_all_low, win_all_high = wilson_interval(wins, total_games)
    finish_low, finish_high = wilson_interval(len(completed), total_games)
    margins = [float(row["margin"]) for row in completed]
    margin_low, margin_high = mean_interval(margins)

    reasons: dict[str, int] = {}
    for row in completed:
        reason = row.get("terminal_reason") or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1

    return {
        "games": total_games,
        "finished": len(completed),
        "finish_ci95": (finish_low, finish_high),
        "stalled": stalls,
        "truncated": truncations,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_rate": wins / len(completed) if completed else float("nan"),
        "win_ci95": (win_low, win_high),
        "win_rate_all": wins / total_games if total_games else float("nan"),
        "win_all_ci95": (win_all_low, win_all_high),
        "mean_vp": float(np.mean(margins)) if margins else float("nan"),
        "vp_ci95": (margin_low, margin_high),
        "terminal_reasons": reasons,
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
    parser.add_argument("--faction", choices=("both", "us", "ussr"), default="both",
                        help="Which factions to evaluate (default: both).")
    parser.add_argument("--safety-only", action="store_true",
                        help="Filter suicide coups and immediate losses for the evaluated policy.")
    parser.add_argument("--adviser", action="store_true",
                        help="Wrap policy with full strategic tactical adviser.")
    parser.add_argument("--schema-version", type=int, choices=(1, 2), default=1,
                        help="Adapter schema version: 1=legacy, 2=v2 (default: 1).")
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
        model_path = "twilight-ppo-v6"
        label = "twilight-ppo-v6"
    elif args.v7:
        model_path = "twilight-ppo-v7"
        label = "twilight-ppo-v7"
    elif args.model:
        model_path = args.model
        label = args.model
    else:
        model_path = None
        label = args.policy

    if model_path:
        raw_selector = model_selector(model_path, deterministic=not args.stochastic)
    else:
        raw_selector = FIXED_POLICIES[args.policy]

    if args.adviser:
        from app.games.twilight_struggle.rl_strategy import make_adviser_wrapped_selector
        selector = make_adviser_wrapped_selector(raw_selector, safety_only=False)
        label = f"{label}+adviser"
    elif args.safety_only:
        from app.games.twilight_struggle.rl_strategy import make_adviser_wrapped_selector
        selector = make_adviser_wrapped_selector(raw_selector, safety_only=True)
        label = f"{label}+safety"
    else:
        selector = raw_selector

    factions = ("us", "ussr") if args.faction == "both" else (args.faction,)

    jsonl_path = Path(args.jsonl_output) if args.jsonl_output else None
    if jsonl_path:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"evaluating {label} games/faction/opponent={args.games} seeds from {args.seed}")
    print(f"{'faction':7} {'opponent':8} {'finished':>9} {'stalled':>7} {'win% [95% CI]':>19} {'win%(all)':>10} {'avg VP [95% CI]':>24} {'finish% [95% CI]':>20} {'sec':>6}")
    for opponent in opponents:
        for faction in factions:
            started = time.time()
            results = [
                play(selector, opponent, faction, args.seed + game, args.max_episode_steps, schema_version=args.schema_version)
                for game in range(args.games)
            ]
            summary = summarize(results)
            if jsonl_path:
                with jsonl_path.open("a", encoding="utf-8") as stream:
                    for row in results:
                        stream.write(json.dumps({"policy": label, **row}, sort_keys=True) + "\n")
            win_lo, win_hi = summary["win_ci95"]
            win_all_lo, win_all_hi = summary["win_all_ci95"]
            margin_lo, margin_hi = summary["vp_ci95"]
            finish_lo, finish_hi = summary["finish_ci95"]
            reasons_str = " ".join(f"{k}:{v}" for k, v in summary["terminal_reasons"].items())
            print(
                f"{faction:7} {opponent:8} {summary['finished']:>4}/{summary['games']:<4} "
                f"{summary['stalled']:>7} {100*summary['win_rate']:>5.1f} [{100*win_lo:>4.1f},{100*win_hi:>4.1f}] "
                f"{100*summary['win_rate_all']:>9.1f}% "
                f"{summary['mean_vp']:>5.1f} [{margin_lo:>5.1f},{margin_hi:>5.1f}] "
                f"{100*summary['finished']/summary['games']:>5.1f} [{100*finish_lo:>4.1f},{100*finish_hi:>4.1f}] "
                f"{time.time() - started:>6.1f}"
            )
            if reasons_str:
                print(f"        terminals: {reasons_str}")


if __name__ == "__main__":
    main()
