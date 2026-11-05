"""Enforcement of cards 27, 41, 93, 94 against the confirmed card reference."""
from copy import deepcopy
import random

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.rules import controlled_by

DATA = load_country_data()
CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _state():
    return {
        "countries": {name: {"us": 0, "ussr": 0} for name in DATA["countries"]},
        "tracks": {"defcon": 5, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
        "turn": 4, "persistent_events": {}, "hands": {"us": [], "ussr": []},
    }


def _activate(state, card_id, faction, choices=None):
    return resolve_card_event(
        state, CARDS[card_id], faction, mode="event", country_data=DATA,
        rng=random.Random(0), event_choices=choices,
    )["game_data"]


@pytest.mark.parametrize("faction", ["us", "ussr"])
@pytest.mark.parametrize("expired", [False, True])
def test_nuclear_subs_only_suppresses_us_defcon_loss_this_turn(faction, expired):
    state = _activate(_state(), 41, "us")
    state["tracks"]["defcon"] = 2
    state["countries"]["Mexico"]["ussr" if faction == "us" else "us"] = 2
    if expired:
        state["turn"] += 1
    before = deepcopy(state)
    after = resolve_operations_action(state, faction, 3, {"type": "coup", "country": "Mexico", "die_roll": 1})
    suppressed = faction == "us" and not expired
    assert after["tracks"]["defcon"] == (2 if suppressed else 1)
    assert after["last_ops_result"]["defcon_loss"] == (0 if suppressed else 1)
    assert (after["terminal_result"] is None) == suppressed
    assert after["tracks"]["military_operations"][faction] == 3
    assert state == before


def test_nuclear_subs_does_not_override_crisis_or_geographic_bans():
    state = _activate(_state(), 41, "us")
    state["tracks"]["defcon"] = 2
    state["countries"]["Mexico"]["ussr"] = 2
    state["countries"]["Japan"]["ussr"] = 2
    state["persistent_events"]["cuban_missile_crisis"] = {"faction": "us", "expires_turn": 4}
    result = resolve_operations_action(state, "us", 3, {"type": "coup", "country": "Mexico", "die_roll": 6})
    assert result["terminal_result"] == {"winner": "ussr", "reason": "cuban_missile_crisis"}
    assert result["countries"] == state["countries"]
    with pytest.raises(ValueError):
        resolve_operations_action(state, "us", 3, {"type": "coup", "country": "Japan", "die_roll": 6})


@pytest.mark.parametrize("soviet_influence", [0, 1, 5])
def test_japan_pact_places_enough_influence_for_control(soviet_influence):
    state = _state()
    state["countries"]["Japan"]["ussr"] = soviet_influence
    after = _activate(state, 27, "us")
    assert controlled_by(after["countries"]["Japan"], DATA["countries"]["Japan"]) == "us"
    assert after["countries"]["Japan"]["us"] == soviet_influence + DATA["countries"]["Japan"]["stability"]


@pytest.mark.parametrize("kind", ["coup", "realignment"])
def test_japan_pact_prohibits_ussr_actions_even_after_us_loses_control(kind):
    state = _activate(_state(), 27, "us")
    state["turn"] = 10  # permanent, not turn-scoped
    state["countries"]["Japan"] = {"us": 1, "ussr": 4}
    action = {"type": kind, "country": "Japan", "die_roll": 6} if kind == "coup" else {
        "type": kind, "targets": [{"country": "Japan", "us_roll": 1, "ussr_roll": 6}],
    }
    before = deepcopy(state)
    with pytest.raises(ValueError, match="Japan"):
        resolve_operations_action(state, "ussr", 3, action)
    assert state == before
    # The pact does not restrict US actions in Japan.
    result = resolve_operations_action(state, "us", 3, action)
    if kind == "coup":
        assert result["terminal_result"] is None


@pytest.mark.parametrize("actor", ["us", "ussr"])
@pytest.mark.parametrize("expired", [False, True])
def test_iran_contra_modifies_us_roll_for_either_actor_and_each_attempt(actor, expired):
    state = _activate(_state(), 93, "ussr")
    state["countries"]["Guatemala"] = {"us": 10, "ussr": 10}
    if expired:
        state["turn"] += 1
    before = deepcopy(state)
    action = {"type": "realignment", "targets": [{"country": "Guatemala", "us_roll": 3, "ussr_roll": 3}] * 2}
    result = resolve_operations_action(state, actor, 2, action)
    for attempt in result["last_ops_result"]["attempts"]:
        assert attempt["rolls"] == {"us": 3, "ussr": 3}
        assert attempt["modifiers"]["us"] == (0 if expired else -1)
    assert result["countries"]["Guatemala"]["us"] == (10 if expired else 7)
    assert state == before


@pytest.mark.parametrize("faction", ["us", "ussr"])
@pytest.mark.parametrize("expired", [False, True])
def test_chernobyl_only_blocks_current_turn_soviet_ops_in_named_region(faction, expired):
    state = _activate(_state(), 94, "us", {"chernobyl": "Asia"})
    state["countries"]["Japan"][faction] = 1
    if expired:
        state["turn"] += 1
    action = {"type": "influence", "placements": [{"country": "Japan", "points": 1}]}
    before = deepcopy(state)
    if faction == "ussr" and not expired:
        with pytest.raises(ValueError, match="Chernobyl"):
            resolve_operations_action(state, faction, 2, action)
    else:
        assert resolve_operations_action(state, faction, 2, action)["countries"]["Japan"][faction] == 2
    assert state == before


def test_chernobyl_rejects_mixed_ops_atomically_but_allows_other_regions_and_events():
    state = _activate(_state(), 94, "us", {"chernobyl": "Asia"})
    state["countries"]["Japan"]["ussr"] = 1
    state["countries"]["Syria"]["ussr"] = 1
    before = deepcopy(state)
    placements = [{"country": "Syria", "points": 1}, {"country": "Japan", "points": 1}]
    with pytest.raises(ValueError, match="Chernobyl"):
        resolve_operations_action(state, "ussr", 3, {"type": "influence", "placements": placements})
    assert state == before
    assert resolve_operations_action(state, "ussr", 2, {"type": "influence", "placements": placements[:1]})["countries"]["Syria"]["ussr"] == 2
    # Korean War influence changes are event effects, not placement of Ops influence.
    state["countries"]["S. Korea"]["us"] = 2
    assert _activate(state, 11, "ussr")["countries"]["S. Korea"]["ussr"] == 2


def test_rl_target_filters_respect_pact_and_chernobyl_without_new_action_ids():
    from app.games.twilight_struggle.rl_adapter import ACTION_COUNT, TwilightStruggleReferenceEnv

    env = TwilightStruggleReferenceEnv()
    env.reset(5)
    gd = env.game_data
    gd["tracks"]["defcon"] = 5
    gd["countries"]["Japan"] = {"us": 2, "ussr": 1}
    gd["persistent_events"]["us_japan_pact"] = True
    gd["persistent_events"]["chernobyl"] = {"region": "Asia", "expires_turn": gd["turn"]}
    assert "Japan" not in env._coup_targets(gd, "ussr")
    assert "Japan" not in env._realign_targets(gd, "ussr")
    assert "Japan" not in env._influence_reachable(gd, "ussr")
    assert "Japan" in env._influence_reachable(gd, "us")
    gd["turn"] += 1
    assert "Japan" in env._influence_reachable(gd, "ussr")
    assert ACTION_COUNT == 781