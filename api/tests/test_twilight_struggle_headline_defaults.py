import random
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.default_choices import candidate_choices
from app.games.twilight_struggle.headlines import resolve_headline_event
from app.games.twilight_struggle.validator import TwilightStruggleValidator

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}
SUEZ_SPACES = ("France", "U.K.", "Israel")


def _gd(us_holdings):
    gd = TwilightStruggleValidator().initial_game_data(7, ["alice", "bob"])
    for name in SUEZ_SPACES:
        gd["countries"][name]["us"] = 0
    for name, value in us_holdings.items():
        gd["countries"][name]["us"] = value
    return gd


def test_default_choices_are_deterministic_without_rng():
    gd = _gd({"France": 1, "U.K.": 2, "Israel": 2})
    first = candidate_choices(gd, CATALOG[28], "us")
    assert first
    assert first == candidate_choices(gd, CATALOG[28], "us")


def test_che_default_targets_require_opponent_influence():
    from app.games.twilight_struggle.cards import load_standard_card_catalog

    data = load_country_data()
    gd = {"countries": {name: {"us": 0, "ussr": 0} for name in data["countries"]}}
    gd["countries"]["Bolivia"]["us"] = 1
    che = next(card for card in load_standard_card_catalog() if card["id"] == 107)

    assert candidate_choices(gd, che, "us") == [{"che": "Bolivia"}]


def test_choice_required_headline_resolves_with_default():
    gd = _gd({"France": 1, "U.K.": 2, "Israel": 2})
    result = resolve_headline_event(
        gd, deepcopy(CATALOG[28]), "us", country_data=DATA, rng=random.Random(0),
    )
    removed = sum(gd["countries"][n]["us"] - result["game_data"]["countries"][n]["us"] for n in SUEZ_SPACES)
    assert removed == 4


def test_headline_with_no_legal_default_is_not_offered_and_fails_closed():
    gd = _gd({})
    with pytest.raises(ValueError):
        resolve_headline_event(gd, deepcopy(CATALOG[28]), "us", country_data=DATA, rng=random.Random(0))

    validator = TwilightStruggleValidator()
    gd["hands"]["us"] = [deepcopy(CATALOG[28])]
    state = {"players": [{"player_id": "alice"}, {"player_id": "bob"}], "game_data": gd}
    offered = [m for m in validator.get_legal_moves(state, "alice") if m.get("card_id") == 28]
    assert offered == []


def test_headline_with_a_legal_default_is_offered():
    gd = _gd({"France": 1, "U.K.": 2, "Israel": 2})
    gd["hands"]["us"] = [deepcopy(CATALOG[28])]
    state = {"players": [{"player_id": "alice"}, {"player_id": "bob"}], "game_data": gd}
    offered = [m for m in TwilightStruggleValidator().get_legal_moves(state, "alice") if m.get("card_id") == 28]
    assert offered
