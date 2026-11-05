"""Profile the dependency-free Lost Cities RL reference environment.

This is intentionally a standalone benchmark. It does not use the API, SQLite,
screen serialization, PettingZoo, or model dependencies.
"""
from __future__ import annotations

import argparse
import gc
import random
import statistics
import time

from app.games.lost_cities.rl_adapter import LostCitiesReferenceEnv


def run_episode(seed: int) -> tuple[int, bool]:
    env = LostCitiesReferenceEnv(seed=seed)
    observation = env.reset()
    steps = 0
    done = False
    rng = random.Random(seed)
    while not done:
        mask = observation["action_mask"]
        legal_actions = [index for index, enabled in enumerate(mask) if enabled]
        if not legal_actions:
            raise RuntimeError(f"no legal actions at step {steps}")
        observation, _, done, _ = env.step(rng.choice(legal_actions))
        steps += 1
    return steps, done


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--trace-memory",
        action="store_true",
        help="Enable tracemalloc; slower and disabled by default.",
    )
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be positive")
    if args.warmup < 0:
        parser.error("--warmup cannot be negative")
    if args.runs < 1:
        parser.error("--runs must be positive")

    for _ in range(args.warmup):
        for offset in range(args.episodes):
            run_episode(args.seed + offset)

    measurements: list[tuple[int, float, int | None]] = []
    for run in range(args.runs):
        gc.collect()
        tracer = None
        if args.trace_memory:
            import tracemalloc
            tracemalloc.start()
            tracer = tracemalloc
        started = time.perf_counter()
        total_steps = 0
        for offset in range(args.episodes):
            steps, done = run_episode(args.seed + offset + run * args.episodes)
            if not done:
                raise RuntimeError("episode did not terminate")
            total_steps += steps
        elapsed = time.perf_counter() - started
        peak = None
        if tracer is not None:
            _, peak = tracer.get_traced_memory()
            tracer.stop()
        measurements.append((total_steps, elapsed, peak))

    rates = [steps / elapsed for steps, elapsed, _ in measurements]
    total_steps = measurements[0][0]
    elapsed = measurements[0][1]
    peak = max((peak for _, _, peak in measurements if peak is not None), default=None)

    print(f"episodes={args.episodes}")
    print(f"warmup_runs={args.warmup}")
    print(f"measured_runs={args.runs}")
    print(f"steps_per_run={total_steps}")
    print(f"average_steps_per_episode={total_steps / args.episodes:.2f}")
    print(f"steps_per_second_runs={[round(rate, 2) for rate in rates]}")
    print(f"steps_per_second_median={statistics.median(rates):.2f}")
    if peak is not None:
        print(f"tracemalloc_peak_bytes_max={peak}")


if __name__ == "__main__":
    main()
