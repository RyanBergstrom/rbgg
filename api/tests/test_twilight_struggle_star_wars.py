from copy import deepcopy

import pytest

from app.games.twilight_struggle import events as events_module
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _state(us_space=0, ussr_space=0, discard_ids=(4, 7)):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    return {
        "countries": countries,
        "tracks": {
            "victory_points": 0,
            "defcon": 5,
            "military_operations": {"us": 0, "ussr": 0},
            "space_race": {"us": us_space, "ussr": ussr_space},
        },
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [deepcopy(CATALOG[i]) for i in discard_ids],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _play(state, choice, phasing="us"):
    return resolve_card_event(
        state, CATALOG[85], phasing, mode="event", country_data=DATA,
        event_choices={"star_wars": choice},
    )


def test_star_wars_is_registered_as_handler():
    assert CATALOG[85]["effect_handler"] == "star_wars"
    assert CATALOG[85]["alignment"] == "us"


def test_no_effect_when_us_not_ahead_on_space_race():
    result = _play(_state(us_space=2, ussr_space=2), 4)
    game = result["game_data"]
    assert _ids(game["discard_pile"]) == [4, 7]


def test_no_effect_when_us_behind_on_space_race():
    result = _play(_state(us_space=1, ussr_space=3), 4)
    assert _ids(result["game_data"]["discard_pile"]) == [4, 7]


def test_chosen_card_must_be_in_discard_pile():
    with pytest.raises(ValueError, match="discard pile"):
        _play(_state(us_space=3, ussr_space=1), 99)


def test_scoring_card_cannot_be_chosen(monkeypatch):
    state = _state(us_space=3, ussr_space=1, discard_ids=())
    scoring = deepcopy(CATALOG[4])
    scoring["scoring"] = True
    state["discard_pile"] = [scoring]
    with pytest.raises(ValueError, match="non-scoring"):
        _play(state, 4)


def test_chosen_event_resolves_for_us_and_then_is_discarded(monkeypatch):
    calls = []
    real_resolve = events_module.resolve_card_event

    def router(game_data, card, phasing, **kwargs):
        if card["id"] == 4:
            calls.append((card["id"], phasing, kwargs["mode"]))
            return {"game_data": game_data, "event_triggered": True, "terminal_result": None}
        return real_resolve(game_data, card, phasing, **kwargs)

    monkeypatch.setattr(events_module, "resolve_card_event", router)
    state = _state(us_space=3, ussr_space=1, discard_ids=(4, 7))
    result = router(state, CATALOG[85], "us", mode="event", country_data=DATA, event_choices={"star_wars": 4})
    game = result["game_data"]
    assert calls == [(4, "us", "event")]
    assert _ids(game["discard_pile"]) == [7, 4]


def test_ussr_cannot_play_star_wars():
    with pytest.raises(ValueError, match="US card"):
        _play(_state(us_space=3, ussr_space=1), 4, phasing="ussr")


def _ids(cards):
    return [c["id"] for c in cards]
