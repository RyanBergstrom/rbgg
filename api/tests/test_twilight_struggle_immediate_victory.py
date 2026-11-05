"""Immediate victory must cross every event/card/headline boundary without later play."""
from copy import deepcopy
import random

import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.headlines import reveal_headlines
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {c["id"]: c for c in load_standard_card_catalog()}


def _state(vp=0, defcon=5):
    gd = TwilightStruggleValidator().initial_game_data(5)
    gd["tracks"]["victory_points"] = vp
    gd["tracks"]["defcon"] = defcon
    gd["hands"] = {"us": [], "ussr": []}
    gd["persistent_events"] = {}
    gd["countries"] = {n: {"us": 0, "ussr": 0} for n in gd["countries"]}
    gd["current_phase"] = "action_round"
    gd["current_player_faction"] = "us"
    gd["current_player"] = "player_1"
    return gd


@pytest.mark.parametrize("cid,faction,start,winner", [
    (97, "us", 19, "us"), (60, "ussr", -19, "ussr"), (58, "ussr", -19, "ussr"),
    (71, "us", 19, "us"), (103, "ussr", 19, "us"), (48, "us", 19, "us"),
    (90, "ussr", -19, "ussr"), (102, "us", 19, "us"),
])
def test_event_families_return_immediate_vp_victory(cid, faction, start, winner):
    state = _state(start)
    state["china_card"] = {"owner": "us" if cid == 71 else "ussr", "face_up": True}
    state["countries"]["Mexico"]["us"] = 10
    before = deepcopy(state)
    result = resolve_card_event(
        state, CARDS[cid], faction, mode="event", rng=random.Random(5),
        event_choices={"iran_iraq_war": "Iran"},
    )
    assert result["terminal_result"] == {"winner": winner, "reason": "twenty_vp"}
    assert state == before


def test_winning_opponent_event_preempts_ordinary_ops():
    state = _state(19)
    state["hands"]["ussr"] = [CARDS[97]]
    result = play_card_action(
        state, "ussr", 97, "operations", rng=random.Random(0),
        operations_action={"type": "influence", "placements": [{"country": "not-a-country", "points": 1}]},
    )
    assert result["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert result["removed_cards"][-1]["id"] == 97


@pytest.mark.parametrize("cid", [4, 50, 89])
def test_defcon_one_preempts_later_vp_and_bonus_flags(cid):
    faction = "ussr" if cid == 50 else "us"
    state = _state(19, 2)
    state["countries"]["S. Korea"]["us"] = 10
    result = resolve_card_event(state, CARDS[cid], faction, mode="event", rng=random.Random(0))
    assert result["terminal_result"] == {"winner": "us" if faction == "ussr" else "ussr", "reason": "defcon_1"}
    assert result["game_data"]["tracks"]["victory_points"] == 19
    assert "kal_007_bonus" not in result["game_data"]["persistent_events"]


def test_nested_five_year_plan_defcon_loss_uses_original_phasing_player():
    state = _state(0, 2)
    state["hands"]["ussr"] = [CARDS[4]]
    result = resolve_card_event(state, CARDS[5], "ussr", mode="event", rng=random.Random(0))
    assert result["terminal_result"] == {"winner": "us", "reason": "defcon_1"}
    assert result["game_data"]["discard_pile"][-1]["id"] == 4


def test_headline_victory_stops_before_second_event():
    state = _state(19)
    state["hands"] = {"us": [CARDS[97]], "ussr": [CARDS[8]]}
    state["headline_cards"] = {"us": 97, "ussr": 8}
    state["current_phase"] = "headline_reveal_ready"
    result = reveal_headlines(state, rng=random.Random(0))
    assert result["current_phase"] == "game_over"
    assert result["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert result["countries"]["Cuba"]["ussr"] == 0
    assert result["hands"]["ussr"][0]["id"] == 8


def test_bury_you_penalty_stops_before_chosen_card_and_rng():
    state = _state(-18)
    state["hands"]["us"] = [CARDS[4]]
    state["persistent_events"]["we_will_bury_you"] = {"faction": "ussr"}
    rng = random.Random(0)
    before_rng = rng.getstate()
    result = play_card_action(state, "us", 4, "event", rng=rng)
    assert result["terminal_result"] == {"winner": "ussr", "reason": "twenty_vp"}
    assert result["hands"]["us"] == [CARDS[4]]
    assert result["tracks"]["defcon"] == 5
    assert rng.getstate() == before_rng


def test_flower_power_terminal_is_not_overwritten_by_none():
    state = _state(-19)
    state["hands"]["us"] = [CARDS[102]]
    state["persistent_events"]["flower_power"] = {"faction": "ussr"}
    result = play_card_action(state, "us", 102, "event", rng=random.Random(1), event_choices={"iran_iraq_war": "Iran"})
    assert result["terminal_result"] == {"winner": "ussr", "reason": "twenty_vp"}


@pytest.mark.parametrize("terminal_shape", ["phase", "result", "flag"])
def test_validator_rejects_moves_after_game_end(terminal_shape):
    state = _state()
    state["hands"]["us"] = [CARDS[97]]
    if terminal_shape == "phase":
        state["current_phase"] = "game_over"
    elif terminal_shape == "result":
        state["terminal_result"] = {"winner": "us", "reason": "twenty_vp"}
    else:
        state["game_over"] = True
    validator = TwilightStruggleValidator()
    envelope = {"game_data": state}
    assert validator.get_legal_moves(envelope, "player_1") == []
    assert not validator.validate_move(envelope, {"type": "play_card", "player_id": "player_1", "card_id": 97, "mode": "event"})


def test_first_terminal_effect_cannot_be_reversed_by_later_effects():
    from app.games.twilight_struggle.country_data import load_country_data
    from app.games.twilight_struggle.events import apply_event_effects

    state = _state(19)
    result = apply_event_effects(state, [
        {"type": "gain_vp", "faction": "us", "amount": 1},
        {"type": "gain_vp", "faction": "ussr", "amount": 5},
        {"type": "add_influence", "faction": "ussr", "country": "Cuba", "amount": 3},
    ], load_country_data())
    assert result["tracks"]["victory_points"] == 20
    assert result["countries"]["Cuba"]["ussr"] == 0
    assert result["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}


def test_nested_phasing_context_is_restored_after_event_failure():
    state = _state(0, 2)
    with pytest.raises(ValueError):
        resolve_card_event(state, CARDS[102], "ussr", mode="event", event_choices={})
    result = resolve_card_event(state, CARDS[4], "us", mode="event")
    assert result["terminal_result"] == {"winner": "ussr", "reason": "defcon_1"}


def test_wargames_specific_ending_is_not_replaced_by_generic_vp_check():
    state = _state(19, 2)
    result = resolve_card_event(state, CARDS[100], "ussr", mode="event", event_choices={"wargames": True})
    assert result["terminal_result"] == {"winner": "us", "reason": "wargames"}


def test_validator_finishes_round_on_penalty_without_consuming_card():
    state = _state(-18)
    state["hands"]["us"] = [CARDS[4]]
    state["persistent_events"]["we_will_bury_you"] = {"faction": "ussr"}
    envelope = {"game_data": state}
    move = {"type": "play_card", "player_id": "player_1", "card_id": 4, "mode": "event"}
    validator = TwilightStruggleValidator()
    assert validator.validate_move(envelope, move)
    after = validator.apply_move(envelope, move)
    assert after["game_data"]["current_phase"] == "game_over"
    assert after["game_data"]["hands"]["us"] == [CARDS[4]]
    assert validator.get_legal_moves(after, "player_1") == []


def test_summit_vp_victory_preempts_optional_defcon_change():
    class Rolls:
        def __init__(self):
            self.values = iter([6, 1])

        def randint(self, low, high):
            return next(self.values)

    state = _state(19, 2)
    result = resolve_card_event(
        state, CARDS[45], "us", mode="event", rng=Rolls(), event_choices={"summit_defcon": -1},
    )
    assert result["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert result["game_data"]["tracks"]["defcon"] == 2


def test_europe_control_preserves_its_specific_terminal_reason():
    from app.games.twilight_struggle.country_data import load_country_data

    state = _state()
    for name, info in load_country_data()["countries"].items():
        if info.get("region") == "Europe":
            state["countries"][name]["us"] = info["stability"]
    result = resolve_card_event(state, CARDS[2], "us", mode="event")
    assert result["terminal_result"] == {"winner": "us", "reason": "europe_control"}