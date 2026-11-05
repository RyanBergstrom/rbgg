from copy import deepcopy

import pytest

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.operations import resolve_operations_action


@pytest.fixture
def base_state():
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Italy"]["ussr"] = 2
    countries["Mexico"]["us"] = 1
    return {
        "countries": countries,
        "tracks": {"defcon": 5, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
    }


def test_coup_ops_action_updates_board_milops_defcon_and_result(base_state):
    before = deepcopy(base_state)
    result = resolve_operations_action(
        base_state,
        "us",
        3,
        {"type": "coup", "country": "Italy", "die_roll": 6},
    )

    assert base_state == before
    assert result["countries"]["Italy"] == {"us": 3, "ussr": 0}
    assert result["tracks"]["military_operations"]["us"] == 3
    assert result["tracks"]["defcon"] == 4
    assert result["terminal_result"] is None


def test_realignment_can_spend_ops_on_multiple_targets(base_state):
    result = resolve_operations_action(
        base_state,
        "us",
        2,
        {
            "type": "realignment",
            "targets": [
                {"country": "Mexico", "us_roll": 6, "ussr_roll": 1},
                {"country": "Italy", "us_roll": 6, "ussr_roll": 1},
            ],
        },
    )

    assert result["operations_spent"] == 2
    assert result["operations_remaining"] == 0
    assert result["countries"]["Mexico"]["ussr"] == 0
    assert result["tracks"]["military_operations"]["us"] == 0


def test_ops_action_rejects_over_budget_or_unknown_modes_atomically(base_state):
    original = deepcopy(base_state)
    with pytest.raises(ValueError, match="within the ops allowance"):
        resolve_operations_action(
            base_state,
            "us",
            1,
            {"type": "realignment", "targets": [{"country": "Mexico", "us_roll": 6, "ussr_roll": 1}] * 2},
        )
    with pytest.raises(ValueError, match="Unsupported operations action"):
        resolve_operations_action(base_state, "us", 2, {"type": "space_race"})
    assert base_state == original


@pytest.mark.parametrize("faction", ["us", "ussr"])
@pytest.mark.parametrize("country", ["Guatemala", "Venezuela", "Angola"])
@pytest.mark.parametrize("owner", ["us", "ussr"])
def test_death_squads_region_and_owner_apply_to_shared_coup_path(base_state, faction, country, owner):
    opponent = "ussr" if faction == "us" else "us"
    base_state["countries"][country][opponent] = 20
    base_state["persistent_events"] = {
        "latin_american_death_squads": {"faction": owner, "expires_turn": 1},
        "salt_negotiations": {"expires_turn": 1},
    }
    result = resolve_operations_action(base_state, faction, 3, {"type": "coup", "country": country, "die_roll": 6})
    regional_modifier = 0 if country == "Angola" else (1 if owner == faction else -1)
    assert result["last_ops_result"]["die_modifier"] == -1 + regional_modifier


@pytest.mark.parametrize("faction", ["us", "ussr"])
def test_crisis_only_affects_restricted_faction_during_its_turn(base_state, faction):
    base_state["persistent_events"] = {"cuban_missile_crisis": {"faction": faction, "expires_turn": 1}}
    base_state["turn"] = 1
    opponent = "ussr" if faction == "us" else "us"
    base_state["countries"]["Guatemala"][opponent] = 1
    before = deepcopy(base_state)
    action = {"type": "coup", "country": "Guatemala", "die_roll": 6}
    result = resolve_operations_action(base_state, faction, 3, action)
    assert result["terminal_result"] == {"winner": opponent, "reason": "cuban_missile_crisis"}
    assert result["countries"] == before["countries"]
    assert result["tracks"]["defcon"] == 1
    assert base_state == before
    base_state["turn"] = 2
    base_state["persistent_events"]["latin_american_death_squads"] = {"faction": faction, "expires_turn": 1}
    result = resolve_operations_action(base_state, faction, 3, action)
    assert result["terminal_result"] is None
    assert result["last_ops_result"]["die_modifier"] == 0
    base_state["turn"] = 1
    base_state["persistent_events"]["cuban_missile_crisis"]["faction"] = opponent
    result = resolve_operations_action(base_state, faction, 3, action)
    assert result["terminal_result"] is None
