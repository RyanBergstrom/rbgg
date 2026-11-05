"""Space Race track: attempts, awards, and first-to-reach special abilities.

Track values follow the printed 2nd Edition board (documentation/twilight-struggle/images/TS Map-11.jpg)
and rules section 6.4. ``tracks["space_race"][faction]`` is the faction's current box (0 = Start, 8 = Space Station).
"""
from __future__ import annotations

import random
from typing import Any

from app.games.twilight_struggle.rules import check_victory_conditions

FACTIONS = ("us", "ussr")
FINAL_BOX = 8
# box: (name, ops needed to attempt it, highest winning d6 roll, VP first, VP second)
SPACE_RACE_BOXES: dict[int, tuple[str, int, int, int, int]] = {
    1: ("Earth Satellite", 2, 3, 2, 1),
    2: ("Animal in Space", 2, 4, 0, 0),
    3: ("Man in Space", 2, 3, 2, 0),
    4: ("Man in Earth Orbit", 2, 4, 0, 0),
    5: ("Lunar Orbit", 3, 3, 3, 1),
    6: ("Eagle/Bear has Landed", 3, 4, 0, 0),
    7: ("Space Shuttle", 3, 3, 4, 2),
    8: ("Space Station", 4, 2, 2, 0),
}
# Special-ability boxes (granted only to the first faction to reach them).
TWO_ATTEMPTS_BOX = 2
HEADLINE_LAST_BOX = 4
DISCARD_HELD_BOX = 6
EIGHT_ROUNDS_BOX = 8


def _positions(game_data: dict[str, Any]) -> dict[str, int]:
    track = (game_data.get("tracks") or {}).get("space_race") or {}
    return {faction: int(track.get(faction, 0)) for faction in FACTIONS}


def other_faction(faction: str) -> str:
    return "ussr" if faction == "us" else "us"


def space_race_vp(box: int, opponent_box: int) -> int:
    """VP for a faction landing on ``box`` while the opponent stands on ``opponent_box``."""
    _, _, _, first, second = SPACE_RACE_BOXES[box]
    return second if opponent_box >= box else first


def has_space_ability(game_data: dict[str, Any], faction: str, box: int) -> bool:
    """True while ``faction`` reached ``box`` first (the opponent has not reached it)."""
    positions = _positions(game_data)
    return positions[faction] >= box and positions[other_faction(faction)] < box


def _turn_bucket(game_data: dict[str, Any], key: str, *, create: bool) -> dict[str, Any]:
    """Per-turn counters stored lazily as ``{"turn": n, ...}``; a bucket from an earlier turn counts as empty."""
    bucket = game_data.get(key)
    turn = game_data.get("turn", 1)
    if isinstance(bucket, dict) and bucket.get("turn") == turn:
        return bucket
    fresh: dict[str, Any] = {"turn": turn}
    if create:
        game_data[key] = fresh
    return fresh


def attempts_this_turn(game_data: dict[str, Any], faction: str) -> int:
    return int(_turn_bucket(game_data, "space_attempts", create=False).get(faction, 0))


def space_attempts_allowed(game_data: dict[str, Any], faction: str) -> int:
    return 2 if has_space_ability(game_data, faction, TWO_ATTEMPTS_BOX) else 1


def headline_blocked_until_opponent(game_data: dict[str, Any], faction: str) -> bool:
    """Man in Earth Orbit: the opponent must commit and show a headline before this faction commits."""
    return has_space_ability(game_data, faction, HEADLINE_LAST_BOX)


def advance_marker_in_place(game_data: dict[str, Any], faction: str, boxes: int) -> int:
    """Move a marker up to ``boxes`` boxes (capped at the final box) and award the landing box's VP.

    Mutates ``game_data`` (callers pass their own clone). Returns the VP awarded.
    """
    tracks = game_data.setdefault("tracks", {})
    track = tracks.setdefault("space_race", {"us": 0, "ussr": 0})
    start = int(track.get(faction, 0))
    landing = min(FINAL_BOX, start + boxes)
    if landing <= start:
        return 0
    opponent_box = int(track.get(other_faction(faction), 0))
    track[faction] = landing
    vp = space_race_vp(landing, opponent_box)
    sign = 1 if faction == "us" else -1
    tracks["victory_points"] = tracks.get("victory_points", 0) + sign * vp
    return vp


def attempt_space_race(
    game_data: dict[str, Any], faction: str, card_operations: int, rng: random.Random,
) -> dict[str, Any]:
    """Spend one Space Race attempt in place. Returns the attempt outcome; raises ValueError if illegal.

    ``game_data`` is mutated (callers pass their own clone). The die is drawn from the server RNG.
    """
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    positions = _positions(game_data)
    position = positions[faction]
    if position >= FINAL_BOX:
        raise ValueError("The Space Race track is complete for this faction")
    target = position + 1
    _, needed_ops, max_roll, _, _ = SPACE_RACE_BOXES[target]
    if card_operations < needed_ops:
        raise ValueError(f"Space Race box {target} needs a card worth at least {needed_ops} Ops")
    attempts = _turn_bucket(game_data, "space_attempts", create=True)
    if attempts.get(faction, 0) >= space_attempts_allowed(game_data, faction):
        raise ValueError("No Space Race attempts remain this turn")
    attempts[faction] = attempts.get(faction, 0) + 1
    roll = rng.randint(1, 6)
    success = roll <= max_roll
    vp = advance_marker_in_place(game_data, faction, 1) if success else 0
    tracks = game_data.get("tracks", {})
    outcome = {
        "type": "space_race", "faction": faction, "target_box": target, "roll": roll,
        "success": success, "vp": vp,
    }
    game_data["last_ops_result"] = outcome
    outcome["terminal_result"] = check_victory_conditions(
        tracks.get("victory_points", 0), tracks.get("defcon", 5), faction,
    )
    return outcome


def record_held_card_decision(game_data: dict[str, Any], faction: str) -> None:
    _turn_bucket(game_data, "held_card_decided", create=True)[faction] = True


def held_card_decision_pending(game_data: dict[str, Any]) -> list[str]:
    """Factions that may still discard a held card (box 6 ability) at the end of this turn."""
    decided = _turn_bucket(game_data, "held_card_decided", create=False)
    hands = game_data.get("hands") or {}
    return [
        faction for faction in ("ussr", "us")
        if has_space_ability(game_data, faction, DISCARD_HELD_BOX)
        and not decided.get(faction)
        and hands.get(faction)
    ]
