"""Count which cards block play when the adapter's mask is empty (stall-cause survey)."""
from __future__ import annotations

import argparse
import random
from collections import Counter

from app.games.twilight_struggle.rl_adapter import TwilightStruggleReferenceEnv
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=60)
    parser.add_argument("--policy", default="random", choices=sorted(FIXED_POLICIES))
    args = parser.parse_args()
    selector = FIXED_POLICIES[args.policy]
    finished = stalled = 0
    event_blocked: Counter = Counter()
    ops_blocked: Counter = Counter()
    both_blocked: Counter = Counter()
    stage_at_stall: Counter = Counter()
    names: dict[int, str] = {}
    for seed in range(args.games):
        env = TwilightStruggleReferenceEnv()
        env.reset(seed)
        rng = random.Random(seed)
        for _ in range(6000):
            if env.is_terminal():
                finished += 1
                break
            legal = [i for i, flag in enumerate(env.action_mask()) if flag]
            if not legal:
                stalled += 1
                gd = env.game_data
                faction = env.faction_of(env.current_player)
                stage_at_stall[(gd["current_phase"], env.stage)] += 1
                for card in gd["hands"].get(faction, []):
                    names[card["id"]] = card["name"]
                    ev = env._event_playable(gd, card, faction) if not card.get("scoring") or True else True
                    ops = card.get("scoring") or env._ops_context(gd, card, faction) is not None
                    if not ev:
                        event_blocked[card["id"]] += 1
                    if not ops:
                        ops_blocked[card["id"]] += 1
                    if not ev and not ops:
                        both_blocked[card["id"]] += 1
                break
            env.step(selector(env, env.observe(env.current_player), rng))
    print(f"games={args.games} finished={finished} stalled={stalled}")
    print("stall (phase, stage):", dict(stage_at_stall))
    print("cards neither playable as event nor ops in stalled hands:")
    for cid, count in both_blocked.most_common(15):
        print(f"  {cid:3} {names[cid]:35} both={count} event_only_blocked={event_blocked[cid] - count} ops_blocked={ops_blocked[cid]}")


if __name__ == "__main__":
    main()
