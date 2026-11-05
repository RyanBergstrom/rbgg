"""Behavioral/strength diagnostics for Bus policies (fixed baselines or models).

Plays full games with one measured policy occupying a configurable set of
seats against an opponent policy in the remaining seats, and reports the
measured policy's average adjusted score (``score - time_stones``), win
rate, and game length. This is the playbook's required "baseline table"
(see ``documentation/rl-game-ai-playbook.md`` section 11/12) that must show
``rule`` clearly beating ``random``/``null`` before any Gym env or training
work begins.

Usage examples::

    python scripts/diagnose_bus_policies.py --policy rule --opponent random --players 3 --episodes 100
    python scripts/diagnose_bus_policies.py --policy rule --opponent null --players 4 --episodes 100
    python scripts/diagnose_bus_policies.py --policy null --opponent random --players 3 --episodes 100
"""
from __future__ import annotations

import argparse
import random
import time
from statistics import mean, pstdev

from app.games.bus.rl_adapter import BusReferenceEnv
from app.games.bus.rl_policies import FIXED_POLICIES


def run_episode(env: BusReferenceEnv, measured_selector, measured_seats, opponent_selector, rng, max_steps):
    observation = env.reset()
    actor = env.current_player
    steps = 0
    while steps < max_steps:
        selector = measured_selector if actor in measured_seats else opponent_selector
        action_id = selector(env, observation, rng)
        observation, _reward, done, info = env.step(action_id)
        steps += 1
        if done:
            return info["final_scores"], info.get("ranking"), steps, True
        actor = env.current_player
    # Episode exceeded max_steps without reaching game_over: treat as a stall.
    data = env.state["game_data"]
    final_scores = {
        pid: player["score"] - player["time_stones"]
        for pid, player in data["players"].items()
    }
    return final_scores, None, steps, False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=sorted(FIXED_POLICIES), required=True,
                         help="measured policy")
    parser.add_argument("--opponent", choices=sorted(FIXED_POLICIES), default="random",
                         help="policy for every other seat")
    parser.add_argument("--players", type=int, default=3, choices=(3, 4, 5))
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--seed", type=int, default=777, help="base seed; each episode uses seed+i")
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--measured-seats", type=int, default=1,
                         help="number of seats (out of --players) the measured policy occupies")
    args = parser.parse_args()

    measured = FIXED_POLICIES[args.policy]
    opponent = FIXED_POLICIES[args.opponent]
    player_ids = tuple(f"player_{i + 1}" for i in range(args.players))
    measured_seats = set(player_ids[: args.measured_seats])
    opponent_seats = set(player_ids) - measured_seats

    rng = random.Random(args.seed)
    own_scores: list[float] = []
    opponent_scores: list[float] = []
    wins = 0
    completed = 0
    stalled = 0
    lengths: list[int] = []

    start_time = time.time()
    for episode in range(args.episodes):
        env = BusReferenceEnv(seed=args.seed + episode, player_ids=player_ids)
        final_scores, winner, steps, done = run_episode(
            env, measured, measured_seats, opponent, rng, args.max_steps,
        )
        lengths.append(steps)
        if not done:
            stalled += 1
            continue
        completed += 1
        own = mean(final_scores[pid] for pid in measured_seats)
        others = mean(final_scores[pid] for pid in opponent_seats) if opponent_seats else 0.0
        own_scores.append(own)
        opponent_scores.append(others)
        if winner in measured_seats:
            wins += 1
    elapsed = time.time() - start_time

    print(f"policy={args.policy} vs opponent={args.opponent} "
          f"players={args.players} measured_seats={args.measured_seats} "
          f"episodes={args.episodes} seed={args.seed}")
    print(f"completed={completed} stalled={stalled} elapsed={elapsed:.1f}s")
    if completed:
        print(f"own_avg_score={mean(own_scores):.2f} (stdev={pstdev(own_scores):.2f})")
        print(f"opponent_avg_score={mean(opponent_scores):.2f} (stdev={pstdev(opponent_scores):.2f})")
        print(f"win_rate={wins / completed:.1%}")
    print(f"avg_game_length={mean(lengths):.1f} steps (min={min(lengths)}, max={max(lengths)})")


if __name__ == "__main__":
    main()
