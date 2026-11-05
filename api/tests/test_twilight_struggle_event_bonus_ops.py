"""Optional event follow-ups execute inline, after primary effects, using server dice."""
from copy import deepcopy
import random

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CARDS = {c["id"]: c for c in load_standard_card_catalog()}


def _state():
    return {
        "countries": {n: {"us": 0, "ussr": 0} for n in DATA["countries"]},
        "tracks": {"defcon": 5, "victory_points": 0, "military_operations": {"us": 1, "ussr": 1}},
        "turn": 4, "persistent_events": {}, "hands": {"us": [], "ussr": []},
    }


def _play(state, cid, faction, choices, rng=None):
    return resolve_card_event(state, CARDS[cid], faction, mode="event", country_data=DATA,
                              event_choices=choices, rng=rng or random.Random(0))


@pytest.mark.parametrize("cid,faction,target,choices", [
    (47, "us", "Mexico", {"junta": "Mexico"}),
    (91, "ussr", "Costa Rica", {}),
    (96, "us", "Italy", {}),
])
def test_free_coup_uses_server_die_no_milops_and_degrades_battleground(cid, faction, target, choices):
    state = _state()
    enemy = "ussr" if faction == "us" else "us"
    state["countries"][target][enemy] = 2
    state["tracks"]["defcon"] = 2
    before = deepcopy(state)
    action = {"type": "coup", "country": target, "die_roll": 1}
    result = _play(state, cid, faction, {**choices, "bonus_operations": action})
    gd = result["game_data"]
    assert gd["last_ops_result"]["die_roll"] == 4  # Random(0), not client-supplied 1
    assert gd["tracks"]["military_operations"] == before["tracks"]["military_operations"]
    expected_defcon = 1 if DATA["countries"][target]["battleground"] else 2
    assert gd["tracks"]["defcon"] == expected_defcon
    assert (result["terminal_result"] is not None) == (expected_defcon == 1)
    assert state == before


@pytest.mark.parametrize("cid,faction,choices,target", [
    (47, "us", {"junta": "Mexico"}, "Japan"),
    (91, "ussr", {}, "Italy"),
    (96, "us", {}, "Mexico"),
])
def test_bonus_rejects_out_of_scope_target_atomically(cid, faction, choices, target):
    state = _state()
    state["countries"][target]["ussr" if faction == "us" else "us"] = 2
    before = deepcopy(state)
    with pytest.raises(ValueError):
        _play(state, cid, faction, {**choices, "bonus_operations": {"type": "coup", "country": target}})
    assert state == before


def test_junta_allows_one_realignment_but_wall_allows_up_to_its_ops():
    state = _state()
    state["countries"]["Italy"]["ussr"] = 8
    state["tracks"]["defcon"] = 2
    targets = [{"country": "Italy"}] * 3
    result = _play(state, 96, "us", {"bonus_operations": {"type": "realignment", "targets": targets}})
    assert len(result["game_data"]["last_ops_result"]["attempts"]) == 3
    with pytest.raises(ValueError):
        _play(state, 47, "us", {"junta": "Mexico", "bonus_operations": {
            "type": "realignment", "targets": [{"country": "Mexico"}] * 2,
        }})


def test_ortega_removes_nicaragua_first_and_cannot_realign():
    state = _state()
    state["countries"]["Nicaragua"]["us"] = 4
    result = _play(state, 91, "ussr", {})
    assert result["game_data"]["countries"]["Nicaragua"]["us"] == 0
    with pytest.raises(ValueError):
        _play(state, 91, "ussr", {"bonus_operations": {"type": "realignment", "targets": [{"country": "Costa Rica"}]}})


def test_olympic_boycott_grants_four_ops_after_defcon_drop():
    state = _state()
    state["countries"]["France"]["us"] = 1
    result = _play(state, 20, "us", {"olympic_games": "boycott", "bonus_operations": {
        "type": "influence", "placements": [{"country": "France", "points": 4}],
    }})
    assert result["game_data"]["countries"]["France"]["us"] == 5
    assert result["game_data"]["tracks"]["defcon"] == 4
    assert result["game_data"]["tracks"]["military_operations"]["us"] == 1


def test_boycott_nuclear_war_preempts_bonus():
    state = _state()
    state["tracks"]["defcon"] = 2
    result = _play(state, 20, "us", {"olympic_games": "boycott", "bonus_operations": {
        "type": "influence", "placements": [{"country": "France", "points": 4}],
    }})
    assert result["terminal_result"] == {"winner": "ussr", "reason": "defcon_1"}
    assert result["game_data"]["countries"] == state["countries"]


def test_olympic_participation_cannot_claim_boycott_bonus():
    with pytest.raises(ValueError):
        _play(_state(), 20, "us", {"olympic_games": "participate", "bonus_operations": {
            "type": "influence", "placements": [],
        }})


@pytest.mark.parametrize("flag", ["salt_negotiations", "latin_american_death_squads", "cuban_missile_crisis"])
def test_free_coup_retains_other_event_restrictions(flag):
    state = _state()
    state["countries"]["Mexico"]["ussr"] = 10
    state["persistent_events"][flag] = {"faction": "us", "expires_turn": 4}
    result = _play(state, 47, "us", {"junta": "Mexico", "bonus_operations": {"type": "coup", "country": "Mexico"}})
    if flag == "cuban_missile_crisis":
        assert result["terminal_result"] == {"winner": "ussr", "reason": "cuban_missile_crisis"}
    else:
        assert result["game_data"]["last_ops_result"]["die_modifier"] == (-1 if flag == "salt_negotiations" else 1)
        assert result["game_data"]["last_ops_result"]["military_operations_earned"] == 0


def test_boycott_coup_is_ordinary_ops_and_earns_military_operations():
    state = _state()
    state["countries"]["Mexico"]["ussr"] = 2
    result = _play(state, 20, "us", {"olympic_games": "boycott", "bonus_operations": {"type": "coup", "country": "Mexico"}})
    assert result["game_data"]["tracks"]["military_operations"]["us"] == 5
    assert result["game_data"]["tracks"]["defcon"] == 3


def test_free_action_uses_active_ops_modifiers():
    state = _state()
    state["countries"]["Mexico"]["ussr"] = 10
    state["persistent_events"]["containment"] = {"faction": "us", "expires_turn": 4}
    result = _play(state, 47, "us", {"junta": "Mexico", "bonus_operations": {"type": "coup", "country": "Mexico"}})
    assert result["game_data"]["last_ops_result"]["coup_margin"] == 4 + 3 - 2 * DATA["countries"]["Mexico"]["stability"]


def test_free_realignment_rejects_overspending_wall_ops():
    with pytest.raises(ValueError):
        _play(_state(), 96, "us", {"bonus_operations": {"type": "realignment", "targets": [{"country": "Italy"}] * 4}})


def test_bonus_with_no_server_rng_fails_closed():
    with pytest.raises(ValueError, match="server RNG"):
        resolve_card_event(_state(), CARDS[47], "us", mode="event", event_choices={
            "junta": "Mexico", "bonus_operations": {"type": "realignment", "targets": [{"country": "Mexico"}]},
        })


def test_validator_inline_bonus_counts_only_one_action_and_ignores_client_dice():
    from app.games.twilight_struggle.validator import TwilightStruggleValidator

    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5)
    gd.update(_state())
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["hands"] = {"us": [CARDS[47]], "ussr": [CARDS[4]]}
    gd["countries"]["Mexico"]["ussr"] = 2
    state = {"game_data": gd}
    move = {
        "type": "play_card", "player_id": "player_1", "card_id": 47, "mode": "event",
        "event_choices": {"junta": "Mexico", "bonus_operations": {"type": "coup", "country": "Mexico", "die_roll": 1}},
    }
    before = deepcopy(state)
    assert validator.validate_move(state, move)
    first = validator.apply_move(state, move)
    move["event_choices"]["bonus_operations"]["die_roll"] = 6
    second = validator.apply_move(state, move)
    assert first == second
    assert first["game_data"]["actions_taken"]["us"] == 1
    assert first["game_data"]["current_player"] == "player_2"
    assert first["game_data"]["discard_pile"][-1]["id"] == 47
    assert state == before


def test_opponent_event_bonus_remains_separate_from_players_ordinary_ops():
    from app.games.twilight_struggle.actions import play_card_action

    state = _state()
    state["hands"]["us"] = [CARDS[91]]
    state["countries"]["Honduras"]["us"] = 5
    state["countries"]["France"]["us"] = 1
    result = play_card_action(
        state, "us", 91, "operations", rng=random.Random(0),
        operations_action={"type": "influence", "placements": [{"country": "France", "points": 2}]},
        event_choices={"bonus_operations": {"type": "coup", "country": "Honduras"}},
    )
    assert result["countries"]["Honduras"]["us"] < 5
    assert result["countries"]["France"]["us"] == 3
    assert result["actions_taken"]["us"] == 1
    assert result["tracks"]["military_operations"] == {"us": 1, "ussr": 1}