"""MCTS benchmark: avg time, iterations, win %, std dev for 100/300/1000 iters.

Also runs full games using the MCTS policy and reports score distributions.

Usage:
    cd api && python -u scripts/benchmark_iters.py
    cd api && python -u scripts/benchmark_iters.py --workers 6 --seeds 5 --score-games 20
"""
import argparse
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    _initial_game_data,
    _calculate_player_score,
    create_deck,
    COLORS,
)
from app.core.mcts import MCTSEngine, MCTSConfig

validator = LostCitiesValidator()

ITER_CONFIGS = [100, 300, 1000]
DEPTH = 500
# NOTE: On Windows, ProcessPoolExecutor spawn overhead dominates for short
# MCTS searches. Use workers=1 for best throughput on Windows. On Linux
# (fork), higher worker counts scale well.


def _start_new_round(game_data):
    deck = create_deck()
    game_data["player_hands"] = {"player_1": deck[:8], "player_2": deck[8:16]}
    game_data["expeditions"] = {
        "player_1": {c: [] for c in COLORS},
        "player_2": {c: [] for c in COLORS},
    }
    game_data["discard_piles"] = {c: [] for c in COLORS}
    game_data["draw_pile"] = deck[16:]
    game_data["current_phase"] = "play_a_card"
    game_data["current_player"] = (
        "player_2"
        if game_data["scores"]["player_2"] > game_data["scores"]["player_1"]
        else "player_1"
    )
    game_data["last_discarded"] = None
    game_data["round_over"] = False
    game_data["pending_draw"] = False


def simulate_full_game(mcts_iters, seed, workers):
    """Play a full game: P1=MCTS, P2=heuristic. Returns (p1_score, p2_score)."""
    random.seed(seed)
    game_data = _initial_game_data()
    mcts_config = MCTSConfig(
        iterations=mcts_iters,
        exploration_constant=1.414,
        max_depth=DEPTH,
        workers=workers,
    )

    while True:
        current_player = game_data.get("current_player", "player_1")
        current_phase = game_data.get("current_phase", "play_a_card")

        if game_data.get("game_over"):
            break

        if game_data.get("round_over"):
            for pid in ["player_1", "player_2"]:
                game_data["scores"][pid] += _calculate_player_score(
                    game_data["expeditions"][pid]
                )
            game_data["round"] += 1
            if game_data["round"] > 3:
                game_data["game_over"] = True
                break
            _start_new_round(game_data)
            continue

        state_dict = {
            "game_data": game_data,
            "current_player_index": 0 if current_player == "player_1" else 1,
            "players": [
                {"player_id": "player_1", "name": "P1"},
                {"player_id": "player_2", "name": "P2"},
            ],
            "version": 0,
        }

        if current_phase == "play_a_card":
            if current_player == "player_1":
                mcts = MCTSEngine(validator, mcts_config)
                result = mcts.search(state_dict, "player_1")
                move = result.move
            else:
                moves = validator.get_legal_moves(state_dict, "player_2")
                exp = [m for m in moves if m["type"] == "play_expedition"]
                if exp:
                    move = max(
                        exp,
                        key=lambda m: (
                            0
                            if m.get("card", "").endswith("_i")
                            else int(m.get("card", "x_0").split("_")[1])
                        ),
                    )
                else:
                    dis = [m for m in moves if m["type"] == "discard"]
                    move = min(
                        dis,
                        key=lambda m: (
                            0
                            if m.get("card", "").endswith("_i")
                            else int(m.get("card", "x_10").split("_")[1])
                        ),
                    )
            game_data = validator.apply_move(state_dict, move)["game_data"]

        elif current_phase == "draw_a_card":
            moves = validator.get_legal_moves(state_dict, current_player)
            draw_pile = [m for m in moves if m["source"] == "draw_pile"]
            move = draw_pile[0] if draw_pile else (moves[0] if moves else None)
            if move is None:
                break
            game_data = validator.apply_move(state_dict, move)["game_data"]

    return game_data["scores"]["player_1"], game_data["scores"]["player_2"]


def print_histogram(scores, label):
    if not scores:
        print("  No scores to display.")
        return

    avg = statistics.mean(scores)
    med = statistics.median(scores)
    mn, mx = min(scores), max(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0

    print(
        f"  Avg: {avg:>7.1f}  Median: {med:>7.1f}  "
        f"Min: {mn:>7.1f}  Max: {mx:>7.1f}  StdDev: {std:>6.1f}"
    )

    bucket_size = 20
    buckets = {}
    for s in scores:
        b = int(s // bucket_size) * bucket_size
        buckets[b] = buckets.get(b, 0) + 1

    lo, hi = min(buckets), max(buckets)
    max_count = max(buckets.values())

    print(f"  {'Score Range':>14}  {'Count':>5}  Distribution")
    print(f"  {'-'*14}  {'-'*5}  {'-'*40}")
    b = lo
    while b <= hi:
        count = buckets.get(b, 0)
        bar_len = int((count / max_count) * 35) if max_count > 0 else 0
        pct = count / len(scores) * 100
        print(
            f"  {b:>5}-{b+bucket_size-1:<5}    {count:>5}  {'#' * bar_len} ({pct:.0f}%)"
        )
        b += bucket_size


def main():
    parser = argparse.ArgumentParser(description="MCTS benchmark with score distributions")
    parser.add_argument("--workers", type=int, default=1, help="MCTS parallel workers (default: 1, use 6 on Linux)")
    parser.add_argument("--seeds", type=int, default=3, help="Seeds for timing benchmark (default: 3)")
    parser.add_argument("--score-games", type=int, default=10, help="Full games per config for score distribution (default: 10)")
    args = parser.parse_args()

    NUM_SEEDS = args.seeds
    NUM_SCORE_GAMES = args.score_games
    WORKERS = args.workers

    # ── Timing benchmark ──────────────────────────────────────────────

    print(f"{'='*90}")
    print(f"MCTS BENCHMARK — {NUM_SEEDS} seeds, depth={DEPTH}, workers={WORKERS}")
    print(f"{'='*90}")
    print(
        f"{'Iters':>6} | {'Avg Time (ms)':>13} | {'Finished':>8} | "
        f"{'Win %':>6} | {'Std Dev':>8}"
    )
    print(f"{'-'*6}-+-{'-'*13}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}")

    for iters in ITER_CONFIGS:
        config = MCTSConfig(
            iterations=iters, exploration_constant=1.414, max_depth=DEPTH, workers=WORKERS
        )
        times = []
        win_rates = []
        total_finished = 0

        for _ in range(NUM_SEEDS):
            seed_val = random.randint(0, 2**31)
            random.seed(seed_val)
            state = {
                "game_data": _initial_game_data(),
                "current_player_index": 0,
                "players": [
                    {"player_id": "player_1", "name": "P1"},
                    {"player_id": "player_2", "name": "P2"},
                ],
                "version": 0,
            }

            mcts = MCTSEngine(validator, config)
            t0 = time.perf_counter()
            result = mcts.search(state, "player_1")
            elapsed = (time.perf_counter() - t0) * 1000

            times.append(elapsed)
            win_rates.append(result.win_rate)
            total_finished += result.finished_rounds

        avg_time = statistics.mean(times)
        avg_wr = statistics.mean(win_rates)
        std_wr = statistics.stdev(win_rates) if len(win_rates) > 1 else 0
        pct_finished = total_finished / (NUM_SEEDS * iters) * 100

        print(
            f"{iters:>6} | {avg_time:>10.1f} ms | {pct_finished:>6.1f}% | "
            f"{avg_wr*100:>5.1f}% | {std_wr*100:>6.1f}%"
        )

    # ── Score distribution from full games ────────────────────────────

    print()
    print(f"{'='*90}")
    print(
        f"SCORE DISTRIBUTION — {NUM_SCORE_GAMES} full games per config "
        f"(P1=MCTS, P2=heuristic, workers={WORKERS})"
    )
    print(f"{'='*90}")

    # Full-game sim is slow at high iteration counts (~18s per MCTS search at
    # 1000 iters, ~24 searches per game). Skip configs above 300 for scoring.
    GAME_ITER_CONFIGS = [c for c in ITER_CONFIGS if c <= 300]
    if not GAME_ITER_CONFIGS:
        print("\n  (no configs eligible for full-game scoring)")
    for iters in GAME_ITER_CONFIGS:
        print(f"\n--- {iters} iterations ---")
        p1_scores = []
        p2_scores = []
        p1_wins = 0

        for g in range(NUM_SCORE_GAMES):
            seed_val = random.randint(0, 2**31)
            t0 = time.perf_counter()
            p1, p2 = simulate_full_game(iters, seed_val, WORKERS)
            elapsed = time.perf_counter() - t0
            p1_scores.append(p1)
            p2_scores.append(p2)
            if p1 > p2:
                p1_wins += 1
            print(f"  Game {g+1:>2}/{NUM_SCORE_GAMES}: P1={p1:>5}  P2={p2:>5}  ({elapsed:.1f}s)")

        print()
        print(f"  MCTS win rate: {p1_wins}/{NUM_SCORE_GAMES} ({p1_wins/NUM_SCORE_GAMES*100:.0f}%)")
        print()
        print(f"  P1 (MCTS) scores:")
        print_histogram(p1_scores, "P1")
        print()
        print(f"  P2 (heuristic) scores:")
        print_histogram(p2_scores, "P2")
        print()

        diffs = [p1 - p2 for p1, p2 in zip(p1_scores, p2_scores)]
        print(f"  Score differential (P1 - P2):")
        print_histogram(diffs, "Diff")
        print()


if __name__ == "__main__":
    main()
