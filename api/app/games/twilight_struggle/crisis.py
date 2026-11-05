"""Card 40's optional influence-removal cancellation at move boundaries."""
from __future__ import annotations

from typing import Any

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy

CANCELLATION_COUNTRIES = {"ussr": ("Cuba",), "us": ("W. Germany", "Turkey")}
LIVE_PHASES = {"headline", "headline_reveal_ready", "action_round", "turn_end", "event_response", "event_bonus", "card_operations"}


def crisis_cancellation_targets(game_data: dict[str, Any], faction: str | None) -> list[str]:
    """Only the restricted faction can pay two of its own influence in one named country."""
    if (
        faction not in CANCELLATION_COUNTRIES
        or game_data.get("game_over")
        or game_data.get("terminal_result") is not None
        or game_data.get("current_phase") not in LIVE_PHASES
    ):
        return []
    crisis = (game_data.get("persistent_events") or {}).get("cuban_missile_crisis")
    if (
        not isinstance(crisis, dict)
        or crisis.get("faction") != faction
        or crisis.get("expires_turn") != game_data.get("turn", 1)
    ):
        return []
    return [
        country for country in CANCELLATION_COUNTRIES[faction]
        if game_data.get("countries", {}).get(country, {}).get(faction, 0) >= 2
    ]


def cancel_cuban_missile_crisis(
    game_data: dict[str, Any], faction: str | None, country: str,
) -> dict[str, Any]:
    """Cancel atomically without spending a card, Ops, action round, or changing the actor/RNG."""
    if country not in crisis_cancellation_targets(game_data, faction):
        raise ValueError("Crisis cancellation requires two own influence in an eligible country")
    result = deepcopy(game_data)
    result["countries"][country][faction] -= 2
    del result["persistent_events"]["cuban_missile_crisis"]
    return result