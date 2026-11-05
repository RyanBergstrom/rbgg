"""Inspect a seeded Twilight RL evaluation stall without exposing hidden state in normal logs."""
from __future__ import annotations

import argparse
import random

import numpy as np

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.default_choices import candidate_choices
from app.games.twilight_struggle.rl_adapter import describe_action
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--model")
    source.add_argument("--policy", choices=sorted(FIXED_POLICIES))
    parser.add_argument("--opponent", required=True, choices=sorted(FIXED_POLICIES))
    parser.add_argument("--faction", required=True, choices=("us", "ussr"))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-episode-steps", type=int, default=6000)
    args = parser.parse_args()

    if args.model:
        from sb3_contrib import MaskablePPO

        model = MaskablePPO.load(args.model, device="cpu")

        def selector(adapter, observation, rng):
            del adapter, rng
            action, _ = model.predict(
                np.asarray(observation["observation"], dtype=np.float32),
                action_masks=np.asarray(observation["action_mask"], dtype=bool),
                deterministic=True,
            )
            return int(action)
    else:
        selector = FIXED_POLICIES[args.policy]
    env = TwilightStruggleGymEnv(
        seed=args.seed,
        opponents={args.opponent: 1.0},
        learner_faction=args.faction,
        max_episode_steps=args.max_episode_steps,
    )
    env.reset(seed=args.seed)
    rng = random.Random(args.seed)
    decisions = 0
    while env.action_masks().any():
        _, _, terminated, truncated, info = env.step(
            selector(env.adapter, env.adapter_observation, rng)
        )
        decisions += 1
        if terminated or (truncated and not info.get("stalled")):
            print(f"finished: terminated={terminated}, truncated={truncated}, decisions={decisions}")
            return

    adapter = env.adapter
    faction = adapter.faction_of(adapter.current_player)
    hand = adapter.game_data.get("hands", {}).get(faction, [])
    raw_legal = adapter.validator.get_legal_moves(adapter.state, adapter.current_player)
    diagnostics = []
    for move in raw_legal:
        card = next((card for card in hand if card.get("id") == move.get("card_id")), None)
        if card is None:
            continue
        candidates = adapter._event_candidates(adapter.game_data, card, faction)
        diagnostics.append({
            "card_id": card["id"],
            "legal_modes": move.get("modes"),
            "candidate_choices": candidate_choices(adapter.game_data, card, faction),
            "event_candidates": candidates,
            "event_playable": adapter._event_playable(adapter.game_data, card, faction),
            "ops_context_available": adapter._ops_context(adapter.game_data, card, faction) is not None,
            "restricted_state": adapter._restricted_state(adapter.game_data, faction, card)[0],
        })
    print("STALL")
    print({
        "seed": args.seed,
        "decisions": decisions,
        "learner": env.learner,
        "learner_faction": env.learner_faction,
        "current_player": adapter.current_player,
        "current_faction": faction,
        "phase": adapter.game_data.get("current_phase"),
        "turn": adapter.game_data.get("turn"),
        "pending": repr(adapter.pending),
        "own_hand": [(card.get("id"), card.get("name"), card.get("operations"), card.get("scoring")) for card in hand],
        "validator_legal_moves": raw_legal,
        "card_diagnostics": diagnostics,
        "adapter_legal_moves": adapter.legal_moves(),
        "adapter_root_option_ids": [
            (action_id, describe_action(action_id)) for action_id in sorted(adapter._root_options())
        ] if adapter.pending is None else [],
    })


if __name__ == "__main__":
    main()
