"""MCTS Turn-1 Benchmark for Lost Cities.

Tests how MCTS performs on the VERY FIRST MOVE of the game across many
random seeds and configurations. This tells you what iterations/depth
produce meaningful differentiation.

Run from api/ directory: python scripts/benchmark_mcts.py
"""
import sys
import os
import time
import random
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import LostCitiesValidator, _initial_game_data
from app.core.mcts import MCTSEngine, MCTSConfig


def make_fresh_state(seed=None):
    """Create a fresh game state dict with a known seed."""
    if seed is not None:
        import random as _rng
        _rng.seed(seed)
    return {
        "game_data": _initial_game_data(),
        "current_player_index": 0,
        "players": [
            {"player_id": "player_1", "name": "P1"},
            {"player_id": "player_2", "name": "P2"},
        ],
        "version": 0,
    }


def benchmark_turn1(iterations, depth, num_seeds=20, workers=1, verbose=False):
    """Run MCTS on turn 1 across many random seeds. Returns stats."""
    validator = LostCitiesValidator()
    config = MCTSConfig(
        iterations=iterations,
        exploration_constant=1.414,
        max_depth=depth,
        workers=workers,
    )

    results = []
    for i in range(num_seeds):
        seed = random.randint(0, 2**31)
        state = make_fresh_state(seed)

        # Verify it's turn 1 (play phase, empty expeditions)
        assert state["game_data"]["current_phase"] == "play_a_card"
        assert state["game_data"]["round"] == 1

        mcts = MCTSEngine(validator, config)
        t0 = time.perf_counter()
        result = mcts.search(state, "player_1")
        elapsed_ms = (time.perf_counter() - t0) * 1000

        mv = result.move
        mv_label = mv.get("type", "") + ":" + mv.get("card", mv.get("source", ""))

        entry = {
            "seed": seed,
            "best_move": mv_label,
            "visits": result.visit_count,
            "win_rate": result.win_rate,
            "search_ms": elapsed_ms,
            "finished": result.finished_rounds,
            "depth_limited": result.depth_limited,
            "total_iters": result.total_iterations,
            "top_moves": result.top_moves,
        }
        results.append(entry)

        if verbose:
            print(f"  [{i+1:2d}/{num_seeds}] {mv_label:>25s}  "
                  f"v={result.visit_count:3d}  wr={result.win_rate:.3f}  "
                  f"fin={result.finished_rounds:3d}/{result.total_iterations}  "
                  f"time={elapsed_ms:7.0f}ms")

    return results


def summarize(results, iterations, depth, workers):
    """Print summary for one configuration."""
    # Move frequency
    move_counts = {}
    for r in results:
        m = r["best_move"]
        move_counts[m] = move_counts.get(m, 0) + 1

    # Win rates
    win_rates = [r["win_rate"] for r in results]
    visit_counts = [r["visits"] for r in results]
    finish_counts = [r["finished"] for r in results]
    search_times = [r["search_ms"] for r in results]

    avg_wr = statistics.mean(win_rates)
    avg_visits = statistics.mean(visit_counts)
    avg_finish = statistics.mean(finish_counts)
    avg_time = statistics.mean(search_times)
    std_wr = statistics.stdev(win_rates) if len(win_rates) > 1 else 0

    # Differentiation: how many unique moves were chosen?
    unique_moves = len(move_counts)

    print(f"  iters={iterations:>5d}  depth={depth:>4d}  workers={workers}  |  "
          f"avg_time={avg_time:>7.0f}ms  "
          f"avg_fin={avg_finish:>5.1f}/{results[0]['total_iters']}  "
          f"avg_wr={avg_wr:.3f}  std_wr={std_wr:.3f}  "
          f"unique_moves={unique_moves}")

    # Move distribution
    sorted_moves = sorted(move_counts.items(), key=lambda x: -x[1])
    move_str = "  ".join(f"{m}:{c}" for m, c in sorted_moves[:6])
    print(f"    Moves: {move_str}")


def run_full_benchmark(seeds=20, workers=1):
    """Run benchmark across multiple configurations."""
    configs = [
        # (iterations, depth)
        (50,   100),
        (50,   200),
        (50,   500),
        (100,  200),
        (100,  500),
        (200,  500),
        (300,  500),
        (500,  500),
        (1000, 500),
    ]

    print("=" * 110)
    print(f"MCTS TURN-1 BENCHMARK — Lost Cities ({seeds} seeds per config, {workers} workers)")
    print("=" * 110)

    all_results = []
    for iters, depth in configs:
        print(f"\n--- iters={iters}, depth={depth}, workers={workers} ---")
        results = benchmark_turn1(iters, depth, num_seeds=seeds, workers=workers, verbose=True)
        summarize(results, iters, depth, workers)
        all_results.append((iters, depth, results))

    # Comparison table
    print("\n" + "=" * 110)
    print("COMPARISON TABLE")
    print("=" * 110)
    print(f"{'Iters':>6} {'Depth':>6} {'Workers':>7} {'Avg Time':>9} {'Avg Finish':>11} "
          f"{'Avg WR':>7} {'Std WR':>7} {'Unique Moves':>13}")
    print("-" * 110)
    for iters, depth, results in all_results:
        avg_time = statistics.mean([r["search_ms"] for r in results])
        avg_fin = statistics.mean([r["finished"] for r in results])
        avg_wr = statistics.mean([r["win_rate"] for r in results])
        std_wr = statistics.stdev([r["win_rate"] for r in results]) if len(results) > 1 else 0
        unique = len(set(r["best_move"] for r in results))
        total_iters = results[0]["total_iters"]

        print(f"{iters:>6} {depth:>6} {workers:>7} {avg_time:>7.0f}ms "
              f"{avg_fin:>8.1f}/{total_iters:<3d} "
              f"{avg_wr:>6.3f} {std_wr:>6.3f} {unique:>12d}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MCTS Turn-1 Benchmark")
    parser.add_argument("--seeds", type=int, default=20, help="Random seeds per config (default: 20)")
    parser.add_argument("--workers", type=int, default=1, help="MCTS parallel workers (default: 1)")
    parser.add_argument("--quick", action="store_true", help="Quick test with fewer configs")
    args = parser.parse_args()

    if args.quick:
        configs = [
            (50, 200), (100, 200), (100, 500),
            (300, 500), (500, 500),
        ]
        print("=" * 110)
        print(f"MCTS TURN-1 BENCHMARK (quick) — {args.seeds} seeds, {args.workers} workers")
        print("=" * 110)
        for iters, depth in configs:
            print(f"\n--- iters={iters}, depth={depth} ---")
            results = benchmark_turn1(iters, depth, num_seeds=args.seeds, workers=args.workers, verbose=True)
            summarize(results, iters, depth, args.workers)
    else:
        run_full_benchmark(seeds=args.seeds, workers=args.workers)
