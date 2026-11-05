"""Opponent-card Ops timing, prevented events, and the shared action-round limit rule."""
from __future__ import annotations

import pytest

from app.games.twilight_struggle.cards import standard_deck
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.state import create_initial_game_data
from app.games.twilight_struggle.turns import faction_action_limit, faction_can_act

CATALOG = {card["id"]: card for card in standard_deck()}


def _state(**overrides):
    state = create_initial_game_data(3)
    state["hands"] = {"us": [], "ussr": []}
    state.update(overrides)
    return state


@pytest.mark.parametrize("card_id", [73, 108])
def test_ussr_playing_a_us_card_for_ops_fires_the_us_event(card_id):
    from app.core.rng import create_rng

    state = _state()
    result = resolve_card_event(state, CATALOG[card_id], "ussr", mode="operations", rng=create_rng(1, "{}"))
    assert result["event_triggered"] is True


@pytest.mark.parametrize("card_id", [73, 108])
def test_ussr_cannot_play_a_us_card_as_an_event(card_id):
    with pytest.raises(ValueError):
        resolve_card_event(_state(), CATALOG[card_id], "ussr", mode="event")


def test_us_playing_a_ussr_card_for_ops_fires_the_ussr_event():
    result = resolve_card_event(_state(), CATALOG[109], "us", mode="operations")
    assert result["event_triggered"] is True
    assert "samantha_yuri" in result["game_data"]["persistent_events"]
    with pytest.raises(ValueError):
        resolve_card_event(_state(), CATALOG[109], "us", mode="event")


def test_prevented_opponent_event_is_skipped_for_ops_but_refused_as_event():
    state = _state(persistent_events={"arab_israeli_war_cancelled": True})
    card = CATALOG[13]  # Arab-Israeli War (USSR event)
    skipped = resolve_card_event(state, card, "us", mode="operations")
    assert skipped["event_triggered"] is False
    with pytest.raises(ValueError, match="Camp David"):
        resolve_card_event(state, card, "ussr", mode="event")


def test_faction_cannot_act_without_cards_or_past_its_limit():
    state = _state(turn=4, actions_taken={"us": 3, "ussr": 3}, hands={"us": [CATALOG[4]], "ussr": []})
    assert faction_can_act(state, "us") is True
    assert faction_can_act(state, "ussr") is False  # empty hand: finished for the turn
    state["actions_taken"]["us"] = 7
    assert faction_can_act(state, "us") is False


def test_north_sea_oil_raises_only_the_us_limit_for_its_turn():
    state = _state(turn=4, persistent_events={"north_sea_oil": {"faction": "us", "expires_turn": 4}})
    assert faction_action_limit(state, "us") == 8
    assert faction_action_limit(state, "ussr") == 7
    state["turn"] = 5
    assert faction_action_limit(state, "us") == 7
