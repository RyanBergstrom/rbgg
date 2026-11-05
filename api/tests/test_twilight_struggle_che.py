from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}
REGIONS = {"Central America", "South America", "Africa"}


class FixedRng:
    def __init__(self, *values):
        self._values = list(values)

    def randint(self, low, high):
        value = self._values.pop(0)
        assert low <= value <= high
        return value


def _eligible(count=2):
    names = [
        name for name, info in DATA["countries"].items()
        if info.get("region") in REGIONS and not info.get("battleground") and isinstance(info.get("stability"), int)
    ]
    assert len(names) >= count
    return names[:count]


def _state(us_by_country):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    for name, us in us_by_country.items():
        countries[name]["us"] = us
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _che(state, choices, rng=None, phasing="ussr"):
    return resolve_card_event(
        state, CATALOG[107], phasing, mode="event", country_data=DATA,
        rng=rng, event_choices=choices,
    )


def test_che_is_registered_as_handler():
    assert CATALOG[107]["effect_handler"] == "che"
    assert CATALOG[107]["operations"] == 3
    assert CATALOG[107]["alignment"] == "ussr"


def test_che_requires_server_rng():
    first, _ = _eligible()
    with pytest.raises(ValueError, match="server RNG"):
        _che(_state({first: 1}), {"che": first})


def test_che_rejects_battleground_target():
    battleground = next(
        name for name, info in DATA["countries"].items()
        if info.get("region") in REGIONS and info.get("battleground")
    )
    with pytest.raises(ValueError, match="non-Battleground"):
        _che(_state({battleground: 1}), {"che": battleground}, rng=FixedRng(6))


def test_che_rejects_middle_east_target():
    target = next(name for name, info in DATA["countries"].items() if info.get("region") == "Middle East")
    with pytest.raises(ValueError, match="non-Battleground"):
        _che(_state({target: 1}), {"che": target}, rng=FixedRng(6))


def test_single_coup_removes_us_influence_and_adds_military_ops():
    first, _ = _eligible()
    state = _state({first: 1})
    result = _che(state, {"che": first}, rng=FixedRng(6))
    game = result["game_data"]
    assert game["countries"][first]["us"] == 0
    assert game["tracks"]["military_operations"]["ussr"] == 3
    assert result["event_triggered"] is True


def test_no_second_coup_when_first_removes_no_us_influence():
    first, second = _eligible()
    state = _state({first: 5, second: 1})
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(1))
    game = result["game_data"]
    assert game["countries"][first]["us"] == 5
    assert game["countries"][second]["us"] == 1
    assert game["tracks"]["military_operations"]["ussr"] == 3


def test_second_coup_happens_when_first_removes_us_influence():
    first, second = _eligible()
    state = _state({first: 1, second: 1})
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(6, 6))
    game = result["game_data"]
    assert game["countries"][first]["us"] == 0
    assert game["countries"][second]["us"] == 0
    # Military Operations track is capped at 5 by existing coup rules (3 + 3 -> 5).
    assert game["tracks"]["military_operations"]["ussr"] == 5


def test_second_coup_must_differ_from_first():
    first, _ = _eligible()
    state = _state({first: 1})
    with pytest.raises(ValueError, match="different country"):
        _che(state, {"che": first, "che_second": first}, rng=FixedRng(6, 6))


def test_second_coup_is_validated_under_same_restrictions():
    first, _ = _eligible()
    battleground = next(
        name for name, info in DATA["countries"].items()
        if info.get("region") in REGIONS and info.get("battleground")
    )
    state = _state({first: 1, battleground: 1})
    with pytest.raises(ValueError, match="non-Battleground"):
        _che(state, {"che": first, "che_second": battleground}, rng=FixedRng(6, 6))


def test_input_state_is_not_mutated():
    first, _ = _eligible()
    state = _state({first: 1})
    before = deepcopy(state)
    _che(state, {"che": first}, rng=FixedRng(6))
    assert state == before


@pytest.mark.parametrize("defcon", [2, 3, 4, 5])
def test_che_chain_is_legal_at_all_live_defcon_levels(defcon):
    first, second = _eligible()
    state = _state({first: 1, second: 1})
    state["tracks"]["defcon"] = defcon
    state["persistent_events"] = {"nato": True, "reformer": {"faction": "ussr"}}
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(6, 6))
    assert result["game_data"]["countries"][second]["us"] == 0
    assert result["game_data"]["tracks"]["defcon"] == defcon


@pytest.mark.parametrize("owner,modifier", [("ussr", 1), ("us", -1)])
def test_che_applies_death_squads_to_both_coups(owner, modifier):
    first, second = "Guatemala", "Nicaragua"
    state = _state({first: 20, second: 20})
    state["persistent_events"]["latin_american_death_squads"] = {"faction": owner, "expires_turn": 1}
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(6, 6))
    for target in (first, second):
        removed = 6 + 3 + modifier - 2 * DATA["countries"][target]["stability"]
        assert result["game_data"]["countries"][target]["us"] == 20 - removed


def test_che_salt_penalty_can_prevent_second_coup():
    first, second = "Costa Rica", "Nicaragua"
    state = _state({first: 1, second: 1})
    state["persistent_events"]["salt_negotiations"] = {"expires_turn": 1}
    # Barely successful without SALT; with SALT the first removes nothing, so no second die is drawn.
    roll = 2 * DATA["countries"][first]["stability"] - 2
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(roll))
    assert result["game_data"]["countries"][first]["us"] == 1
    assert result["game_data"]["countries"][second]["us"] == 1


@pytest.mark.parametrize("modifier", [-1, 1])
def test_che_uses_modified_operations_for_both_coups(modifier):
    first, second = "Guatemala", "Nicaragua"
    state = _state({first: 20, second: 20})
    name = "red_scare_purge" if modifier < 0 else "brezhnev_doctrine"
    state["persistent_events"][name] = {"faction": "ussr", "expires_turn": 1}
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(6, 6))
    for target in (first, second):
        removed = 6 + 3 + modifier - 2 * DATA["countries"][target]["stability"]
        assert result["game_data"]["countries"][target]["us"] == 20 - removed


def test_che_crisis_loses_without_applying_first_coup_or_rolling_second():
    first, second = _eligible()
    state = _state({first: 1, second: 1})
    state["persistent_events"]["cuban_missile_crisis"] = {"faction": "ussr", "expires_turn": 1}
    result = _che(state, {"che": first, "che_second": second}, rng=FixedRng(6))
    assert result["terminal_result"] == {"winner": "us", "reason": "cuban_missile_crisis"}
    assert result["game_data"]["countries"] == state["countries"]


def test_invalid_second_coup_leaves_input_unchanged():
    first, _ = _eligible()
    state = _state({first: 1})
    before = deepcopy(state)
    with pytest.raises(ValueError):
        _che(state, {"che": first, "che_second": "Iran"}, rng=FixedRng(6))
    assert state == before
