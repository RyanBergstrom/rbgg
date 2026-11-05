from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.operations import resolve_operations_action

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _names(region, count):
    names = [n for n, info in DATA["countries"].items() if info.get("region") == region]
    assert len(names) >= count
    return names[:count]


def _state(vp=0, us=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    for name, values in (us or {}).items():
        countries[name]["us"] = values
    return {
        "countries": countries,
        "tracks": {"victory_points": vp, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _reform(state, placement, phasing="ussr"):
    return resolve_card_event(
        state, CATALOG[87], phasing, mode="event", country_data=DATA,
        event_choices={"reformer": placement},
    )


def test_reformer_is_registered_as_handler():
    assert CATALOG[87]["effect_handler"] == "reformer"
    assert CATALOG[87]["alignment"] == "ussr"


def test_places_four_ussr_influence_by_default():
    a, b = _names("Europe", 2)
    result = _reform(_state(vp=0), {a: 2, b: 2})
    game = result["game_data"]
    assert game["countries"][a]["ussr"] == 2
    assert game["countries"][b]["ussr"] == 2
    assert game["persistent_events"]["reformer"]["faction"] == "ussr"


def test_places_six_when_ussr_ahead_on_vp():
    a, b, c = _names("Europe", 3)
    result = _reform(_state(vp=-2), {a: 2, b: 2, c: 2})
    game = result["game_data"]
    assert game["countries"][a]["ussr"] + game["countries"][b]["ussr"] + game["countries"][c]["ussr"] == 6


def test_four_rejected_when_ussr_ahead():
    a, b = _names("Europe", 2)
    with pytest.raises(ValueError, match="exactly 6"):
        _reform(_state(vp=-1), {a: 2, b: 2})


def test_six_rejected_when_not_ahead():
    a, b, c = _names("Europe", 3)
    with pytest.raises(ValueError, match="exactly 4"):
        _reform(_state(vp=0), {a: 2, b: 2, c: 2})


def test_more_than_two_per_country_rejected():
    a, b = _names("Europe", 2)
    with pytest.raises(ValueError, match="max 2 per country"):
        _reform(_state(vp=0), {a: 3, b: 1})


def test_non_european_target_rejected():
    africa = _names("Africa", 1)[0]
    a, b = _names("Europe", 2)
    with pytest.raises(ValueError, match="cannot target"):
        _reform(_state(vp=0), {africa: 2, a: 2})


def test_empty_placement_rejected():
    with pytest.raises(ValueError, match="requires"):
        _reform(_state(vp=0), {})


def test_us_cannot_play_reformer():
    a, b = _names("Europe", 2)
    with pytest.raises(ValueError, match="USSR card"):
        _reform(_state(vp=0), {a: 2, b: 2}, phasing="us")


def test_ussr_coup_in_europe_is_banned_after_reformer():
    european = _names("Europe", 1)[0]
    state = _state(us={european: 1})
    state["persistent_events"]["reformer"] = {"faction": "ussr"}
    with pytest.raises(ValueError, match="Reformer"):
        resolve_operations_action(
            state, "ussr", 3, {"type": "coup", "country": european, "die_roll": 6}, DATA,
        )


def test_ussr_coup_outside_europe_still_allowed_after_reformer():
    africa = next(
        n for n, info in DATA["countries"].items()
        if info.get("region") == "Africa" and not info.get("battleground") and isinstance(info.get("stability"), int)
    )
    state = _state(us={africa: 1})
    state["persistent_events"]["reformer"] = {"faction": "ussr"}
    result = resolve_operations_action(
        state, "ussr", 3, {"type": "coup", "country": africa, "die_roll": 6}, DATA,
    )
    assert result["countries"][africa]["us"] == 0


def test_european_coup_allowed_without_reformer():
    european = _names("Europe", 1)[0]
    state = _state(us={european: 1})
    result = resolve_operations_action(
        state, "ussr", 3, {"type": "coup", "country": european, "die_roll": 6}, DATA,
    )
    assert result["countries"][european]["us"] == 0
