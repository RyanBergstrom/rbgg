"""Cards 26, 57, 62 and 90: ordinary bonus Ops, timing, and private hand reveals."""
from copy import deepcopy
import random

import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.serialize import serialize_game_state

DATA = load_country_data()
CARDS = {c["id"]: c for c in load_standard_card_catalog()}


def _state():
    return {
        "countries": {n: {"us": 0, "ussr": 0} for n in DATA["countries"]},
        "tracks": {"defcon": 3, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [CARDS[4]], "ussr": [CARDS[8]]}, "turn": 4,
        "persistent_events": {}, "draw_pile": [CARDS[57]],
        "headline_cards": {"us": 4, "ussr": None},
    }


def _play(state, cid, faction, action=None):
    return resolve_card_event(
        state, CARDS[cid], faction, mode="event", rng=random.Random(0),
        event_choices={} if action is None else {"bonus_operations": action},
    )


@pytest.mark.parametrize("cid,faction,ops", [(57, "us", 4), (57, "ussr", 4), (26, "us", 1), (62, "ussr", 1), (90, "ussr", 4)])
def test_event_grants_ordinary_ops_without_spending_an_extra_round(cid, faction, ops):
    state = _state()
    state["countries"]["France"][faction] = 1
    if cid == 90:
        state["persistent_events"]["reformer"] = {"faction": "ussr"}
    before = deepcopy(state)
    result = _play(state, cid, faction, {"type": "influence", "placements": [{"country": "France", "points": ops}]})
    assert result["game_data"]["countries"]["France"][faction] == 1 + ops
    assert "actions_taken" not in result["game_data"]
    assert result["game_data"]["tracks"]["defcon"] == (4 if cid in {57, 90} else 3)
    assert state == before


@pytest.mark.parametrize("cid,faction,points,flag", [(26, "us", 2, "containment"), (62, "ussr", 2, "brezhnev_doctrine"), (57, "us", 3, "red_scare_purge")])
def test_bonus_ops_modifiers_apply_to_beneficiary(cid, faction, points, flag):
    state = _state()
    state["countries"]["France"][faction] = 1
    state["persistent_events"][flag] = {"faction": faction, "expires_turn": 4}
    result = _play(state, cid, faction, {"type": "influence", "placements": [{"country": "France", "points": points}]})
    assert result["game_data"]["countries"]["France"][faction] == 1 + points
    with pytest.raises(ValueError):
        _play(state, cid, faction, {"type": "influence", "placements": [{"country": "France", "points": points + 1}]})


def test_abm_defcon_improvement_precedes_coup_and_bonus_is_not_free():
    state = _state()
    state["tracks"]["defcon"] = 2
    state["countries"]["Iran"]["ussr"] = 5
    result = _play(state, 57, "us", {"type": "coup", "country": "Iran", "die_roll": 1})
    assert result["game_data"]["tracks"]["defcon"] == 2
    assert result["game_data"]["tracks"]["military_operations"]["us"] == 4
    assert result["game_data"]["last_ops_result"]["die_roll"] == 4
    # ABM does not waive geographic DEFCON bans: Europe is still blocked at DEFCON 3.
    state["countries"]["Italy"]["ussr"] = 5
    with pytest.raises(ValueError):
        _play(state, 57, "us", {"type": "coup", "country": "Italy"})


def test_glasnost_bonus_requires_reformer_and_never_allows_coups():
    state = _state()
    state["countries"]["France"]["ussr"] = 1
    action = {"type": "influence", "placements": [{"country": "France", "points": 4}]}
    with pytest.raises(ValueError, match="Reformer"):
        _play(state, 90, "ussr", action)
    state["persistent_events"]["reformer"] = {"faction": "ussr"}
    state["countries"]["Mexico"]["us"] = 1
    with pytest.raises(ValueError):
        _play(state, 90, "ussr", {"type": "coup", "country": "Mexico"})


def test_glasnost_twenty_vp_preempts_bonus_and_ends_game():
    state = _state()
    state["tracks"]["victory_points"] = -19
    state["persistent_events"]["reformer"] = {"faction": "ussr"}
    result = _play(state, 90, "ussr", {"type": "influence", "placements": [{"country": "France", "points": 4}]})
    assert result["terminal_result"] == {"winner": "ussr", "reason": "twenty_vp"}
    assert result["game_data"]["countries"] == state["countries"]


@pytest.mark.parametrize("cid,player,beneficiary,loser", [(26, "ussr", "us", "ussr"), (62, "us", "ussr", "us")])
def test_opponent_bonus_coup_defcon_loss_belongs_to_phasing_player(cid, player, beneficiary, loser):
    state = _state()
    state["tracks"]["defcon"] = 2
    state["hands"][player] = [CARDS[cid]]
    state["countries"]["Mexico"][player] = 5
    result = play_card_action(
        state, player, cid, "operations", rng=random.Random(0),
        event_choices={"bonus_operations": {"type": "coup", "country": "Mexico"}},
        operations_action={"type": "influence", "placements": [{"country": "France", "points": 1}]},
    )
    assert result["terminal_result"] == {"winner": beneficiary, "reason": "defcon_1"}
    assert result["countries"]["France"][loser] == 0
    assert result["actions_taken"][player] == 1


@pytest.mark.parametrize("cid,beneficiary,victim", [(26, "us", "ussr"), (62, "ussr", "us")])
def test_hand_reveal_only_reaches_beneficiary_and_is_detached(cid, beneficiary, victim):
    state = _state()
    before = deepcopy(state)
    after = _play(state, cid, beneficiary)["game_data"]
    view = serialize_game_state(after, beneficiary)
    assert view["revealed_hands"] == {victim: state["hands"][victim]}
    view["revealed_hands"][victim].clear()
    assert serialize_game_state(after, beneficiary)["revealed_hands"][victim] == state["hands"][victim]
    for viewer in (victim, None, "invalid"):
        safe = serialize_game_state(after, viewer)
        assert "revealed_hands" not in safe
        assert "_event_hand_reveals" not in safe
        assert not {"draw_pile", "headline_cards", "rng_seed", "rng_state_json"} & safe.keys()
    after["turn"] += 1
    assert "revealed_hands" not in serialize_game_state(after, beneficiary)
    assert state == before


def test_cia_turn_reveal_updates_but_lone_gunman_is_a_snapshot():
    for cid, beneficiary, victim in [(26, "us", "ussr"), (62, "ussr", "us")]:
        state = _state()
        after = _play(state, cid, beneficiary)["game_data"]
        after["hands"][victim].append(CARDS[57])
        revealed = serialize_game_state(after, beneficiary)["revealed_hands"][victim]
        assert (CARDS[57] in revealed) == (cid == 26)


@pytest.mark.parametrize("cid,faction", [(26, "us"), (62, "ussr")])
def test_one_op_bonus_cannot_spend_two_without_a_modifier(cid, faction):
    state = _state()
    state["countries"]["France"][faction] = 1
    before = deepcopy(state)
    with pytest.raises(ValueError):
        _play(state, cid, faction, {"type": "influence", "placements": [{"country": "France", "points": 2}]})
    assert state == before


def test_glasnost_supports_four_realignment_rolls_but_not_five():
    state = _state()
    state["persistent_events"]["reformer"] = {"faction": "ussr"}
    state["countries"]["Guatemala"] = {"us": 10, "ussr": 10}
    result = _play(state, 90, "ussr", {"type": "realignment", "targets": [{"country": "Guatemala"}] * 4})
    assert len(result["game_data"]["last_ops_result"]["attempts"]) == 4
    assert result["game_data"]["tracks"]["military_operations"] == {"us": 0, "ussr": 0}
    with pytest.raises(ValueError):
        _play(state, 90, "ussr", {"type": "realignment", "targets": [{"country": "Guatemala"}] * 5})


def test_lone_gunman_snapshot_excludes_the_played_card_and_preserves_private_rng():
    state = _state()
    state["hands"]["us"] = [CARDS[62], CARDS[4]]
    state["countries"]["France"]["us"] = 1
    result = play_card_action(
        state, "us", 62, "operations", rng=random.Random(0),
        operations_action={"type": "influence", "placements": [{"country": "France", "points": 1}]},
    )
    view = serialize_game_state(result, "ussr")
    assert [c["id"] for c in view["revealed_hands"]["us"]] == [4]
    assert "_event_hand_reveals" not in view
    # Changes to authoritative cards after serialization must not alter the delivered knowledge.
    result["_event_hand_reveals"]["lone_gunman"]["cards"].clear()
    assert [c["id"] for c in view["revealed_hands"]["us"]] == [4]


def test_validator_handles_abm_bonus_with_one_card_action_and_seeded_rng():
    from app.games.twilight_struggle.validator import TwilightStruggleValidator

    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5)
    gd.update(_state())
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["hands"] = {"us": [CARDS[57]], "ussr": [CARDS[8]]}
    gd["countries"]["Iran"]["ussr"] = 5
    move = {
        "type": "play_card", "player_id": "player_1", "card_id": 57, "mode": "event",
        "event_choices": {"bonus_operations": {"type": "coup", "country": "Iran", "die_roll": 1}},
    }
    state = {"game_data": gd}
    before = deepcopy(state)
    assert validator.validate_move(state, move)
    first = validator.apply_move(state, move)
    move["event_choices"]["bonus_operations"]["die_roll"] = 6
    assert validator.apply_move(state, move) == first
    assert first["game_data"]["actions_taken"] == {"us": 1, "ussr": 0}
    assert first["game_data"]["current_player"] == "player_2"
    assert state == before