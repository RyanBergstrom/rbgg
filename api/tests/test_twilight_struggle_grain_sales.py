from copy import deepcopy

import pytest

from app.games.twilight_struggle import events as events_module
from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


class FixedRng:
    """Returns queued die values; mirrors random.Random.randint."""

    def __init__(self, *values):
        self._values = list(values)

    def randint(self, low, high):
        value = self._values.pop(0)
        assert low <= value <= high
        return value


DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _grain_card():
    return deepcopy(CATALOG[67])


def _ussr_card(card_id):
    return deepcopy(CATALOG[card_id])


def _state(ussr_hand=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [_grain_card()], "ussr": ussr_hand if ussr_hand is not None else []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "actions_taken": {"us": 0, "ussr": 0},
        "turn": 1,
    }


def test_grain_sales_is_registered_as_handler():
    assert CATALOG[67]["effect_handler"] == "grain_sales"
    assert CATALOG[67]["operations"] == 2
    assert CATALOG[67]["alignment"] == "us"


def test_grain_sales_with_empty_ussr_hand_lets_ops_proceed():
    result = resolve_card_event(_state(), _grain_card(), "us", mode="operations", country_data=DATA, rng=FixedRng())
    assert result["event_triggered"] is False
    assert result["ops_skipped"] is False
    assert result["terminal_result"] is None


def test_grain_sales_return_leaves_ussr_hand_and_lets_ops_proceed():
    state = _state([_ussr_card(4), _ussr_card(8)])
    result = resolve_card_event(
        state, _grain_card(), "us", mode="operations", country_data=DATA,
        rng=FixedRng(1), event_choices={"grain_sales": "return"},
    )
    assert result["ops_skipped"] is False
    assert [card["id"] for card in result["game_data"]["hands"]["ussr"]] == [4, 8]
    assert result["game_data"]["discard_pile"] == []


def test_grain_sales_defaults_to_return_when_no_choice_given():
    state = _state([_ussr_card(4)])
    result = resolve_card_event(state, _grain_card(), "us", mode="operations", country_data=DATA, rng=FixedRng(1))
    assert result["ops_skipped"] is False
    assert [card["id"] for card in result["game_data"]["hands"]["ussr"]] == [4]


def test_grain_sales_play_resolves_drawn_card_as_us_event_and_skips_ops(monkeypatch):
    original = events_module.resolve_card_event
    calls = []

    def fake(game_data, card, phasing, **kwargs):
        if card["id"] == 8:
            calls.append((card["id"], phasing, kwargs["mode"]))
            return {"game_data": game_data, "event_triggered": True, "terminal_result": None}
        return original(game_data, card, phasing, **kwargs)

    monkeypatch.setattr(events_module, "resolve_card_event", fake)
    played = _ussr_card(8)
    played["event_removed"] = False
    state = _state([_ussr_card(4), played])
    result = resolve_card_event(
        state, _grain_card(), "us", mode="operations", country_data=DATA,
        rng=FixedRng(2), event_choices={"grain_sales": "play"},
    )
    game = result["game_data"]
    assert calls == [(8, "us", "event")]
    assert result["ops_skipped"] is True
    assert [card["id"] for card in game["hands"]["ussr"]] == [4]
    assert game["discard_pile"][-1]["id"] == 8


def test_grain_sales_play_of_event_removed_card_goes_to_removed_cards(monkeypatch):
    monkeypatch.setattr(
        events_module, "resolve_card_event",
        lambda game_data, card, phasing, **kwargs: {"game_data": game_data, "event_triggered": True, "terminal_result": None},
    )
    removed = _ussr_card(8)
    removed["event_removed"] = True
    result = resolve_card_event(
        _state([removed]), _grain_card(), "us", mode="operations", country_data=DATA,
        rng=FixedRng(1), event_choices={"grain_sales": "play"},
    )
    assert result["game_data"]["removed_cards"][-1]["id"] == 8
    assert result["game_data"]["discard_pile"] == []


def test_grain_sales_play_rejects_scoring_card():
    scoring = _ussr_card(8)
    scoring["scoring"] = True
    with pytest.raises(ValueError, match="scoring"):
        resolve_card_event(
            _state([scoring]), _grain_card(), "us", mode="operations", country_data=DATA,
            rng=FixedRng(1), event_choices={"grain_sales": "play"},
        )


def test_grain_sales_requires_server_rng():
    with pytest.raises(ValueError, match="server RNG"):
        resolve_card_event(
            _state([_ussr_card(4)]), _grain_card(), "us", mode="operations", country_data=DATA, rng=None,
        )


def test_grain_sales_rejects_invalid_choice():
    with pytest.raises(ValueError, match="play or return"):
        resolve_card_event(
            _state([_ussr_card(4)]), _grain_card(), "us", mode="operations", country_data=DATA,
            rng=FixedRng(1), event_choices={"grain_sales": "maybe"},
        )


def test_grain_sales_cannot_be_played_as_event():
    with pytest.raises(ValueError, match="Operations-only"):
        resolve_card_event(_state(), _grain_card(), "us", mode="event", country_data=DATA, rng=FixedRng())


def test_play_card_action_skips_grain_sales_ops_when_drawn_card_is_played(monkeypatch):
    original = events_module.resolve_card_event

    def fake(game_data, card, phasing, **kwargs):
        if card["id"] == 8:
            return {"game_data": game_data, "event_triggered": True, "terminal_result": None}
        return original(game_data, card, phasing, **kwargs)

    monkeypatch.setattr(events_module, "resolve_card_event", fake)
    state = _state([_ussr_card(8)])
    result = play_card_action(
        state, "us", 67, "operations",
        operations_action={"type": "influence", "placements": []},
        country_data=DATA, rng=FixedRng(1), event_choices={"grain_sales": "play"},
    )
    assert result["last_card_play"]["operations_result"] is None
    assert result["actions_taken"]["us"] == 1
    assert result["discard_pile"][-1]["id"] == 67
    assert result["hands"]["ussr"] == []
