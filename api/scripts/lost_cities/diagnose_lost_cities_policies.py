"""Behavioral diagnostics for Lost Cities policies (models and fixed baselines).

Reports per player-round expedition behavior, cycling, value-head calibration
and, for legacy v1 models, hand-order sensitivity. With ``--opponent`` the
measured policy plays one seat against a fixed opponent and only that seat's
behavior is reported; otherwise it plays both seats.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from statistics import mean

import numpy as np
import torch

from app.games.lost_cities.rl_adapter import (
    LostCitiesReferenceEnv,
    _can_extend,
    action_id_for_move,
    encode_observation,
)
from app.games.lost_cities.rl_policies import (
    FIXED_POLICIES,
    make_model_selector,
    observation_version_for_size,
)
from app.games.lost_cities.validator import (
    LostCitiesValidator,
    _calculate_expedition_score,
    is_investment,
)

ROUND_KEYS = (
    "round_score", "expeditions", "negative_expeditions", "negative_total",
    "positive_total", "cards_per_expedition", "investments", "plays", "starts",
    "late_starts", "discards", "feeding_discards", "discard_draws", "cycles",
)


def hand_order_agreement(model, env, rng) -> bool | None:
    """Return whether the chosen card is unchanged after shuffling hand order."""
    game_data = env.state["game_data"]
    if game_data["current_phase"] != "play_a_card":
        return None
    me = env.current_player
    hand = list(game_data["player_hands"][me])

    def chosen_card(order: list[str]) -> tuple[str, str]:
        state = {
            **env.state,
            "game_data": {**game_data, "player_hands": {**game_data["player_hands"], me: order}},
        }
        obs = encode_observation(state, me, env.validator.get_legal_moves(state, me), env.observation_version)
        action, _ = model.predict(
            np.asarray(obs["observation"], dtype=np.float32),
            action_masks=np.asarray(obs["action_mask"], dtype=bool),
            deterministic=True,
        )
        action = int(action)
        return ("play" if action < 8 else "discard"), order[action % 8]

    shuffled = hand[:]
    rng.shuffle(shuffled)
    return chosen_card(hand) == chosen_card(shuffled)


def run_policy(name, selector, episodes, seed, starting_player, model=None,
               version=2, opponent=None, focus_seat=None):
    """Play ``episodes`` games; ``focus_seat=None`` means the policy plays both seats."""
    rng = random.Random(seed)
    rounds: list[dict] = []
    finals: list[dict[str, int]] = []
    agreements: list[bool] = []
    value_pairs: list[tuple[float, float]] = []
    steps_list: list[int] = []

    for episode in range(episodes):
        env = LostCitiesReferenceEnv(
            seed=seed + episode,
            starting_player=starting_player,
            validator=LostCitiesValidator(),
            observation_version=version,
        )
        observation = env.reset()
        per_player = {pid: defaultdict(float) for pid in env.agents}
        last_discard_draw: dict[str, str | None] = {pid: None for pid in env.agents}
        episode_values: list[tuple[str, float]] = []
        steps = 0
        done = False
        while not done and steps < 1500:
            game_data = env.state["game_data"]
            me = env.current_player
            measured = focus_seat is None or me == focus_seat
            if model is not None and measured:
                if version == 1 and steps % 7 == 0:
                    agreement = hand_order_agreement(model, env, rng)
                    if agreement is not None:
                        agreements.append(agreement)
                vector = np.asarray(observation["observation"], dtype=np.float32)[None, :]
                with torch.no_grad():
                    value = model.policy.predict_values(torch.as_tensor(vector, device=model.device)).item()
                episode_values.append((me, value))

            action = (selector if measured else opponent)(env, observation, rng)
            move = next(m for m in env.legal_moves(me) if action_id_for_move(m) == action)
            stats = per_player[me]
            remaining = len(game_data["draw_pile"])
            round_ending = move["type"] == "draw" and move["source"] == "draw_pile" and remaining == 1
            if move["type"] == "play_expedition":
                stats["plays"] += 1
                if not game_data["expeditions"][me][move["color"]]:
                    stats["starts"] += 1
                    if remaining <= 15:
                        stats["late_starts"] += 1
                last_discard_draw[me] = None
            elif move["type"] == "discard":
                stats["discards"] += 1
                other = "player_2" if me == "player_1" else "player_1"
                their_cards = game_data["expeditions"][other][move["color"]]
                if their_cards and _can_extend(their_cards, move["card"]):
                    stats["feeding_discards"] += 1
                if last_discard_draw[me] == move["card"]:
                    stats["cycles"] += 1
                last_discard_draw[me] = None
            elif move["source"] != "draw_pile":
                stats["discard_draws"] += 1
                color = move["source"].replace("_discard", "")
                last_discard_draw[me] = game_data["discard_piles"][color][-1]

            if round_ending:
                for pid in env.agents:
                    if focus_seat is not None and pid != focus_seat:
                        continue
                    started = [cards for cards in game_data["expeditions"][pid].values() if cards]
                    scores = [_calculate_expedition_score(cards) for cards in started]
                    record = dict(per_player[pid])
                    record.update(
                        round_score=sum(scores),
                        expeditions=len(started),
                        negative_expeditions=sum(score < 0 for score in scores),
                        negative_total=sum(score for score in scores if score < 0),
                        positive_total=sum(score for score in scores if score > 0),
                        cards_per_expedition=mean(len(cards) for cards in started) if started else 0.0,
                        investments=sum(is_investment(card) for cards in started for card in cards),
                    )
                    rounds.append(record)
                per_player = {pid: defaultdict(float) for pid in env.agents}

            observation, _, done, info = env.step(action)
            steps += 1
        steps_list.append(steps)
        if done:
            scores = info["final_scores"]
            finals.append(scores)
            for actor, value in episode_values:
                other = "player_2" if actor == "player_1" else "player_1"
                value_pairs.append((value, scores[actor] - scores[other]))

    def avg(key: str) -> float:
        return round(mean(record.get(key, 0.0) for record in rounds), 2) if rounds else 0.0

    report = {
        "policy": name,
        "opponent": "self" if focus_seat is None else opponent.__name__.removeprefix("choose_"),
        "starting_player": starting_player,
        "episodes": episodes,
        "finished": len(finals),
        "avg_steps": round(mean(steps_list), 1),
    }
    if focus_seat is None:
        report["avg_game_score_per_player"] = (
            round(mean((s["player_1"] + s["player_2"]) / 2 for s in finals), 2) if finals else None
        )
    else:
        other = "player_2" if focus_seat == "player_1" else "player_1"
        report["seat"] = focus_seat
        report["avg_game_score"] = round(mean(s[focus_seat] for s in finals), 2) if finals else None
        report["avg_opponent_score"] = round(mean(s[other] for s in finals), 2) if finals else None
        report["win_rate"] = round(mean(s[focus_seat] > s[other] for s in finals), 3) if finals else None
    report["per_player_round"] = {key: avg(key) for key in ROUND_KEYS}
    if agreements:
        report["hand_order_agreement"] = round(sum(agreements) / len(agreements), 3)
    if len(value_pairs) > 2:
        values, margins = zip(*value_pairs)
        report["value_vs_final_margin_corr"] = round(float(np.corrcoef(values, margins)[0, 1]), 3)
        report["value_mean"] = round(float(mean(values)), 3)
        report["value_std"] = round(float(np.std(values)), 3)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--model", action="append", default=[], help="name=path.zip")
    parser.add_argument("--skip-baselines", action="store_true")
    parser.add_argument("--opponent", choices=sorted(FIXED_POLICIES),
                        help="Measure one seat against this fixed policy instead of self-play.")
    args = parser.parse_args()

    policies = []
    if not args.skip_baselines:
        policies += [(name, selector, None, 2) for name, selector in FIXED_POLICIES.items()]
    for spec in args.model:
        from sb3_contrib import MaskablePPO

        name, path = spec.split("=", 1)
        model = MaskablePPO.load(path, device="cpu")
        version = observation_version_for_size(model.observation_space.shape[0])
        model_selector = make_model_selector(model)
        policies.append((name, lambda env, obs, rng, choose=model_selector: choose(env, obs, rng), model, version))

    opponent = FIXED_POLICIES.get(args.opponent) if args.opponent else None
    for name, selector, model, version in policies:
        # The measured policy sits in player_1; alternate who starts the game.
        for starting_player in ("player_1", "player_2"):
            report = run_policy(
                name, selector, args.episodes, args.seed, starting_player, model, version,
                opponent=opponent, focus_seat="player_1" if opponent else None,
            )
            print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
