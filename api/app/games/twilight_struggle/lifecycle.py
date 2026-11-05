"""Turn-end maintenance for Twilight Struggle's ten-turn card lifecycle."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
import random
from typing import Any

from app.core.rng import create_rng
from app.games.twilight_struggle.cards import standard_deck
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.rules import award_military_operations_penalty, check_victory_conditions
from app.games.twilight_struggle.scoring import calculate_major_region_final_score
from app.games.twilight_struggle.space_race import headline_blocked_until_opponent
from app.games.twilight_struggle.turns import (
    cards_entering_era,
    deal_to_hand_limit,
    faction_can_act,
    insert_era_cards,
    start_turn_tracks,
)

FACTIONS = ("us", "ussr")


def finish_turn(
    game_data: dict[str, Any],
    country_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply end-turn military penalty, then deal/advance or final-score.

    This is a deterministic transition; RNG is restored from and serialized
    into game data. Scoring cards must be cleared and both faction action-round
    counts must be complete before a turn can close.
    """
    turn = game_data.get("turn")
    if not isinstance(turn, int) or not 1 <= turn <= 10:
        raise ValueError("turn must be between 1 and 10")
    if any(faction_can_act(game_data, faction) for faction in FACTIONS):
        raise ValueError("both factions must complete the turn's action rounds")
    hands = game_data.get("hands", {})
    if any(card.get("scoring") for faction in FACTIONS for card in hands.get(faction, [])):
        raise ValueError("scoring cards must be played before the turn can end")

    result = deepcopy(game_data)
    result["persistent_events"] = {
        name: event
        for name, event in result.get("persistent_events", {}).items()
        if not isinstance(event, dict)
        or not isinstance(event.get("expires_turn"), int)
        or event["expires_turn"] > turn
    }
    tracks = result.get("tracks", {})
    penalty = award_military_operations_penalty(tracks.get("military_operations", {}), tracks.get("defcon", 5))
    tracks["victory_points"] += penalty["vp_delta_us"]
    tracks["military_operations"] = penalty["reset_military_operations"]
    result["last_military_operations_penalty"] = penalty
    result.setdefault("china_card", {})["face_up"] = True

    terminal = check_victory_conditions(
        tracks["victory_points"], tracks.get("defcon", 5), result.get("current_player_faction", "us")
    )
    if terminal is not None:
        result["current_phase"] = "game_over"
        result["terminal_result"] = terminal
        result["tracks"] = tracks
        return result

    if turn == 10:
        final = calculate_major_region_final_score(
            tracks["victory_points"],
            result.get("countries", {}),
            country_data or load_country_data(),
            china_card_owner=result.get("china_card", {}).get("owner"),
            formosan_resolution=bool((result.get("persistent_events") or {}).get("formosan_resolution")),
        )
        if not final["complete"]:
            raise ValueError(final["incomplete_reason"])
        tracks["victory_points"] = final["final_vp_us_relative"]
        result["final_scoring"] = final
        result["terminal_result"] = {"winner": final["winner"], "reason": final["reason"]}
        result["current_phase"] = "game_over"
        result["tracks"] = tracks
        return result

    next_turn = turn + 1
    result = start_turn_tracks(result, next_turn)
    result["current_player_faction"] = "ussr"
    era = cards_entering_era(next_turn)
    rng = create_rng(result.get("rng_seed", 42), result.get("rng_state_json", "{}"))
    if era in {2, 3}:
        result = insert_era_cards(result, next_turn, standard_deck(era), rng)
    result = deal_to_hand_limit(result, next_turn, rng)
    result["current_phase"] = "headline"
    # Man in Earth Orbit (Space Race box 4): the opponent of its holder commits and shows a headline first.
    first = "us" if headline_blocked_until_opponent(result, "ussr") else "ussr"
    result["current_player_faction"] = first
    result["current_player"] = result.get("player_by_faction", {}).get(first, first)
    result["terminal_result"] = None
    return result
