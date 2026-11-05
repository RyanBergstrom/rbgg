"""Fixed Lost Cities policies for RL opponents, teachers, and evaluation.

Every selector follows the shared runner signature
``selector(adapter, observation, rng) -> action_id`` and returns an action ID in
the adapter's fixed action space.
"""
from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np

from app.games.lost_cities.rl_adapter import LEGACY_OBSERVATION_SIZE, action_id_for_move
from app.games.lost_cities.validator import COLORS, card_color, card_number, is_investment

Selector = Callable[[Any, dict[str, Any], random.Random], int]


def _last_number(expedition: list[str]) -> int | None:
    return max(
        (number for number in (card_number(card) for card in expedition) if number is not None),
        default=None,
    )


def choose_random(adapter, observation, rng: random.Random) -> int:
    del adapter
    return rng.choice([index for index, enabled in enumerate(observation["action_mask"]) if enabled])


def choose_never_play(adapter, observation, rng: random.Random) -> int:
    """Always discard slot 0 and draw from the deck: the 0-point floor."""
    del rng
    mask = observation["action_mask"]
    if adapter.state["game_data"]["current_phase"] == "play_a_card":
        return 8
    return 16 if mask[16] else next(index for index, enabled in enumerate(mask) if enabled)


def choose_rule(adapter, observation, rng: random.Random) -> int:
    """Commitment-aware rule policy used as opponent, teacher, and benchmark.

    It continues expeditions with small gaps, starts at most strong colors
    early in a round, discards dead or low-potential cards that do not feed
    the opponent, and only takes discards that extend an open expedition.
    """
    del observation, rng
    game_data = adapter.state["game_data"]
    me = adapter.current_player
    opponent = "player_2" if me == "player_1" else "player_1"
    hand = game_data["player_hands"][me]
    mine = game_data["expeditions"][me]
    theirs = game_data["expeditions"][opponent]
    remaining = len(game_data["draw_pile"])
    legal = adapter.legal_moves(me)

    if game_data["current_phase"] == "draw_a_card":
        for move in legal:
            if move["source"] == "draw_pile":
                continue
            color = move["source"].replace("_discard", "")
            top = game_data["discard_piles"][color][-1]
            last = _last_number(mine[color])
            if (
                mine[color]
                and not is_investment(top)
                and last is not None
                and 0 < card_number(top) - last <= 2
            ):
                return action_id_for_move(move)
        draw = [move for move in legal if move["source"] == "draw_pile"]
        return action_id_for_move(draw[0] if draw else legal[0])

    plays = [move for move in legal if move["type"] == "play_expedition"]
    best_continue = None
    for move in plays:
        color = move["color"]
        if not mine[color]:
            continue
        if is_investment(move["card"]):
            gap = 0
        else:
            last = _last_number(mine[color])
            gap = card_number(move["card"]) - (last if last is not None else 1)
        if (gap <= 2 or remaining <= 8) and (best_continue is None or gap < best_continue[0]):
            best_continue = (gap, move)
    if best_continue:
        return action_id_for_move(best_continue[1])

    if remaining >= 20:
        for color in COLORS:
            if mine[color]:
                continue
            in_color = [card for card in hand if card_color(card) == color]
            total = sum(card_number(card) or 0 for card in in_color)
            if total >= 22 and len(in_color) >= 3:
                start = min(
                    (move for move in plays if move["color"] == color),
                    key=lambda move: 0 if is_investment(move["card"]) else card_number(move["card"]),
                )
                return action_id_for_move(start)

    def discard_cost(move: dict[str, Any]) -> tuple[int, int]:
        card = move["card"]
        color = move["color"]
        number = card_number(card) or 0
        last_theirs = _last_number(theirs[color])
        helps_opponent = bool(theirs[color]) and (last_theirs is None or number > last_theirs)
        own_potential = sum(card_number(c) or 0 for c in hand if card_color(c) == color)
        if mine[color]:
            last_mine = _last_number(mine[color])
            dead = last_mine is not None and (is_investment(card) or number <= last_mine)
            own_potential = 0 if dead else 100
        return (1 if helps_opponent else 0, own_potential)

    discards = [move for move in legal if move["type"] == "discard"]
    return action_id_for_move(min(discards, key=discard_cost))


FIXED_POLICIES: dict[str, Selector] = {
    "random": choose_random,
    "never_play": choose_never_play,
    "rule": choose_rule,
}


def observation_version_for_size(size: int) -> int:
    """Infer the adapter observation schema a saved model was trained on."""
    return 1 if size == LEGACY_OBSERVATION_SIZE else 2


def make_model_selector(model, deterministic: bool = True) -> Selector:
    """Wrap a MaskablePPO model as a runner-compatible selector."""

    def choose(adapter, observation, rng: random.Random) -> int:
        del adapter, rng
        action, _ = model.predict(
            np.asarray(observation["observation"], dtype=np.float32),
            action_masks=np.asarray(observation["action_mask"], dtype=bool),
            deterministic=deterministic,
        )
        return int(action)

    return choose


def make_seat_selector(seat: str, seat_selector: Selector, other_selector: Selector) -> Selector:
    """Route decisions by the adapter's active player."""

    def choose(adapter, observation, rng: random.Random) -> int:
        selector = seat_selector if adapter.current_player == seat else other_selector
        return selector(adapter, observation, rng)

    return choose
