"""Fixed Bus policies for RL opponents, teachers, and evaluation.

Every selector follows the shared runner signature
``selector(adapter, observation, rng) -> action_id`` and returns an action ID
in the adapter's fixed action space (``app.games.bus.rl_adapter``).
"""
from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np

from app.games.bus.rl_adapter import OBSERVATION_SIZES, action_id_for_move
from app.games.bus.validator import BUILDING_SITES, EDGES, STATION_CROSSINGS

Selector = Callable[[Any, dict[str, Any], random.Random], int]

# Resolution action types, most to least valuable for a simple rule-of-thumb
# bot: scoring (vrrooomm) first, then growing the network, then supporting
# moves, then the lowest-impact single-slot actions.
_ACTION_TYPE_PRIORITY = (
    "vrrooomm", "line_expansion", "buildings", "passengers",
    "buses", "clock", "starting_player",
)


def observation_version_for_size(size: int) -> int:
    """Infer the schema version from a saved model's observation length."""
    for version, expected in OBSERVATION_SIZES.items():
        if expected == size:
            return version
    raise ValueError(f"no Bus observation schema matches size {size}")


def choose_random(adapter, observation, rng: random.Random) -> int:
    del adapter
    enabled = [index for index, flag in enumerate(observation["action_mask"]) if flag]
    return rng.choice(enabled)


def choose_null(adapter, observation, rng: random.Random) -> int:
    """The most passive legal action: end the current obligation immediately."""
    del rng
    actor = adapter.current_player
    legal = adapter.legal_moves(actor)
    for preferred_type in ("pass_action_selection", "complete_resolution", "clock_advance"):
        for move in legal:
            if move["type"] == preferred_type:
                return action_id_for_move(move)
    if not legal:
        enabled = [index for index, flag in enumerate(observation["action_mask"]) if flag]
        return enabled[0]
    return action_id_for_move(min(legal, key=action_id_for_move))


def _edge_touches_unbuilt_zone1_site(edge_id: str) -> bool:
    """True when extending this edge reaches a crossing with an open zone-1 site."""
    zone1_crossings = {
        site["crossing"] for site in BUILDING_SITES.values() if site["zone"] == 1
    }
    return bool(zone1_crossings.intersection(EDGES[edge_id]))


def choose_rule(adapter, observation, rng: random.Random) -> int:
    """Original stable rule policy used by the v1-v3 teachers and baselines."""
    del observation, rng
    data = adapter.state["game_data"]
    me = adapter.current_player
    legal = adapter.legal_moves(me)
    if not legal:
        raise ValueError("no legal moves available for the rule policy")
    phase = data.get("current_phase")

    if phase == "SETUP_BUILDINGS":
        # Favor 'house' first (serves the starting clock type most often).
        preferred = sorted(legal, key=lambda m: (m["building_type"] != "house", m["site_id"]))
        return action_id_for_move(preferred[0])

    if phase in ("SETUP_FIRST_ROUTE_SEGMENTS", "SETUP_SECOND_ROUTE_SEGMENTS"):
        ranked = sorted(
            legal,
            key=lambda m: (0 if _edge_touches_unbuilt_zone1_site(m["edge_id"]) else 1, m["edge_id"]),
        )
        return action_id_for_move(ranked[0])

    if phase == "ACTION_SELECTION":
        select_moves = [move for move in legal if move["type"] == "select_action"]
        pass_moves = [move for move in legal if move["type"] == "pass_action_selection"]
        if select_moves:
            for action_type in _ACTION_TYPE_PRIORITY:
                for move in select_moves:
                    if move["action_type"] == action_type:
                        return action_id_for_move(move)
            return action_id_for_move(select_moves[0])
        return action_id_for_move(pass_moves[0])

    if phase == "RESOLVE_LINE_EXPANSION":
        expansions = [move for move in legal if move["type"] == "line_expand"]
        if not expansions:
            return action_id_for_move(legal[0])
        unbuilt_crossings = {
            site["crossing"] for site_id, site in BUILDING_SITES.items()
            if site_id not in data.get("buildings", {})
        }
        ranked = sorted(
            expansions,
            key=lambda move: (
                0 if any(crossing in unbuilt_crossings for crossing in EDGES[move["edge_id"]]) else 1,
                move["edge_id"],
            ),
        )
        return action_id_for_move(ranked[0])

    if phase == "RESOLVE_BUILDINGS":
        builds = [move for move in legal if move["type"] == "build"]
        if not builds:
            return action_id_for_move(legal[0])
        ranked = sorted(
            builds,
            key=lambda move: (
                0 if move.get("building_type") == data.get("clock") else 1,
                move["site_id"], move["building_type"],
            ),
        )
        return action_id_for_move(ranked[0])

    if phase == "RESOLVE_CLOCK":
        for move in legal:
            if move["type"] == "clock_advance":
                return action_id_for_move(move)
        return action_id_for_move(legal[0])

    if phase == "RESOLVE_VRROOMM":
        ranked = sorted(legal, key=action_id_for_move)
        return action_id_for_move(ranked[0])

    # Buses, passengers, starting_player resolution, and any other phase:
    # take the first canonically ordered legal option.
    return action_id_for_move(min(legal, key=action_id_for_move))


FIXED_POLICIES: dict[str, Selector] = {
    "random": choose_random,
    "null": choose_null,
    "rule": choose_rule,
}


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
    """Route decisions by the adapter's active player (seat vs. every other seat)."""

    def choose(adapter, observation, rng: random.Random) -> int:
        selector = seat_selector if adapter.current_player == seat else other_selector
        return selector(adapter, observation, rng)

    return choose
