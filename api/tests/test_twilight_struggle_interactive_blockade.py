"""Blockade belongs to USSR; its discard-or-remove response belongs only to US."""
from copy import deepcopy
import json
import random

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {c["id"]: c for c in load_standard_card_catalog()}


def _state():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5)
    gd.update(current_phase="action_round", current_player="player_2", current_player_faction="ussr")
    gd["hands"] = {"us": [CARDS[4], CARDS[8], CARDS[2]], "ussr": [CARDS[10], CARDS[57]]}
    gd["countries"]["W. Germany"] = {"us": 4, "ussr": 1}
    return validator, {"game_data": gd}


def _start(v, state, **extra):
    move = {"type": "play_card", "card_id": 10, "player_id": "player_2", "mode": "event", "interactive": True, **extra}
    assert v.validate_move(state, move)
    return v.apply_move(state, move)


def test_commit_waits_for_us_and_does_not_remove_influence_or_advance_rng():
    v, state = _state()
    before = deepcopy(state)
    staged = _start(v, state)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == "player_1"
    assert gd["countries"] == state["game_data"]["countries"]
    assert gd["rng_state_json"] == state["game_data"]["rng_state_json"]
    assert [c["id"] for c in gd["hands"]["ussr"]] == [57]
    assert gd.get("actions_taken", {}).get("ussr", 0) == 0
    assert not v.get_legal_moves(staged, "player_2")
    assert state == before


@pytest.mark.parametrize("discard", [True, False])
def test_response_matches_inline_preserves_single_action_and_card_removal(discard):
    v, state = _state()
    staged = _start(v, state)
    response = {"type": "event_response", "player_id": "player_1", "decision": "discard" if discard else "remove_influence"}
    if discard:
        response["card_id"] = 4
    assert v.validate_move(staged, response)
    after = v.apply_move(staged, response)
    inline = {"type": "play_card", "player_id": "player_2", "card_id": 10, "mode": "event",
              "event_choices": {"blockade": 4} if discard else {}}
    assert after == v.apply_move(state, inline)
    gd = after["game_data"]
    assert gd["countries"]["W. Germany"] == {"us": 4 if discard else 0, "ussr": 1}
    assert gd["actions_taken"] == {"us": 0, "ussr": 1}
    assert gd["removed_cards"][-1]["id"] == 10
    if discard:
        assert gd["discard_pile"][-1]["id"] == 4  # Discarded card's event is not triggered.
    assert not v.validate_move(after, response)


@pytest.mark.parametrize("modifier,eligible", [(None, True), ("red_scare_purge", False), ("containment", True)])
def test_discard_choices_use_us_modified_ops_not_printed_value(modifier, eligible):
    v, state = _state()
    if modifier:
        state["game_data"]["persistent_events"][modifier] = {"faction": "us", "expires_turn": 1}
    staged = _start(v, state)
    offered = v.get_legal_moves(staged, "player_1")
    ids = {m.get("card_id") for m in offered if m["decision"] == "discard"}
    assert (4 in ids) == eligible
    assert (8 in ids) == (modifier == "containment")
    assert 2 not in ids
    for move in offered:
        assert v.validate_move(staged, move)
    forged = {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 4}
    assert v.validate_move(staged, forged) == eligible


@pytest.mark.parametrize("bad", ["owner", "opponent_card", "scoring", "china", "choice", "extra_ops", "decline_with_card"])
def test_invalid_response_is_rejected_without_mutation(bad):
    v, state = _state()
    staged = _start(v, state)
    move = {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 4}
    if bad == "owner":
        move["player_id"] = "player_2"
    elif bad == "opponent_card":
        move["card_id"] = 57
    elif bad == "scoring":
        move["card_id"] = 2
    elif bad == "china":
        move["card_id"] = 6
    elif bad == "choice":
        move["decision"] = "participate"
    elif bad == "extra_ops":
        move["operations_action"] = {"type": "influence", "placements": []}
    else:
        move["decision"] = "remove_influence"
    before = deepcopy(staged)
    assert not v.validate_move(staged, move)
    with pytest.raises(ValueError):
        v.apply_move(staged, move)
    assert staged == before


def test_no_eligible_card_still_allows_us_to_acknowledge_removal():
    v, state = _state()
    state["game_data"]["hands"]["us"] = []
    staged = _start(v, state)
    moves = v.get_legal_moves(staged, "player_1")
    assert moves == [{"type": "event_response", "player_id": "player_1", "decision": "remove_influence"}]
    assert v.apply_move(staged, moves[0])["game_data"]["countries"]["W. Germany"]["us"] == 0


def test_pending_state_roundtrips_without_exposing_us_discard_options_to_ussr():
    v, state = _state()
    staged = _start(v, state)
    restored = json.loads(json.dumps(staged))
    for viewer in ("us", "ussr", None):
        view = serialize_game_state(restored["game_data"], viewer)
        assert view["pending_event"]["card_id"] == 10
        assert view["pending_event"]["responding_player"] == "player_1"
        assert "_pending_event" not in view
        assert not {"hands", "draw_pile", "headline_cards", "rng_state_json"} & view.keys()
        assert "eligible_discards" not in view["pending_event"]
        assert view["hand"] == (restored["game_data"]["hands"][viewer] if viewer else None)
    move = {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 4}
    assert v.apply_move(restored, move) == v.apply_move(staged, move)


def test_only_ussr_event_mode_is_advertised_and_accepted():
    v, state = _state()
    assert next(m for m in v.get_legal_moves(state, "player_2") if m.get("card_id") == 10)["interactive_modes"] == ["event"]
    move = {"type": "play_card", "player_id": "player_2", "card_id": 10, "mode": "operations", "interactive": True}
    assert not v.validate_move(state, move)
    state["game_data"]["hands"]["us"] = [CARDS[10]]
    state["game_data"].update(current_player="player_1", current_player_faction="us")
    assert not v.validate_move(state, {**move, "mode": "event", "player_id": "player_1"})


def test_inline_blockade_uses_same_modified_discard_rules():
    _, state = _state()
    gd = state["game_data"]
    gd["persistent_events"]["containment"] = {"faction": "us", "expires_turn": 1}
    result = resolve_card_event(gd, CARDS[10], "ussr", mode="event", event_choices={"blockade": 8}, rng=random.Random(0))
    assert result["game_data"]["discard_pile"][-1]["id"] == 8
    gd["persistent_events"] = {"red_scare_purge": {"faction": "us", "expires_turn": 1}}
    with pytest.raises(ValueError, match="3\\+ Ops"):
        resolve_card_event(gd, CARDS[10], "ussr", mode="event", event_choices={"blockade": 4})


@pytest.mark.parametrize("seed,success", [(1, True), (5, False)])
def test_bear_trap_gate_runs_once_before_blockade_response(seed, success):
    v, state = _state()
    gd = state["game_data"]
    gd["rng_seed"], gd["rng_state_json"] = seed, "{}"
    gd["persistent_events"]["action_restriction"] = {"faction": "ussr"}
    staged = _start(v, state, restriction_discard_id=57)
    assert staged["game_data"]["discard_pile"][-1]["id"] == 57
    if success:
        assert staged["game_data"]["current_phase"] == "event_response"
        result = v.apply_move(staged, {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 4})
        assert result["game_data"]["actions_taken"]["ussr"] == 1
        assert [c["id"] for c in result["game_data"]["discard_pile"]] == [57, 4]
    else:
        assert "_pending_event" not in staged["game_data"]
        assert staged["game_data"]["actions_taken"]["ussr"] == 1
        assert any(c["id"] == 10 for c in staged["game_data"]["hands"]["ussr"])
        assert staged["game_data"]["countries"]["W. Germany"]["us"] == 4


def test_last_action_response_can_close_the_turn_without_second_action():
    v, state = _state()
    gd = state["game_data"]
    gd["hands"] = {"us": [CARDS[4]], "ussr": [CARDS[10]]}
    gd["actions_taken"] = {"us": 6, "ussr": 5}
    staged = _start(v, state)
    # Pending response must still be offered to a US faction whose action rounds are complete.
    move = next(m for m in v.get_legal_moves(staged, "player_1") if m["decision"] == "discard")
    after = v.apply_move(staged, move)["game_data"]
    assert after["current_phase"] == "turn_end"
    assert after["actions_taken"] == {"us": 6, "ussr": 6}
    assert after["hands"] == {"us": [], "ussr": []}
    assert "_pending_event" not in after


def test_expired_ops_modifier_does_not_change_discard_eligibility():
    v, state = _state()
    state["game_data"]["persistent_events"]["red_scare_purge"] = {"faction": "us", "expires_turn": 0}
    staged = _start(v, state)
    ids = {m.get("card_id") for m in v.get_legal_moves(staged, "player_1") if m["decision"] == "discard"}
    assert ids == {4}


def test_cannot_repeat_commit_or_inject_discard_choice_at_start():
    v, state = _state()
    base = {"type": "play_card", "card_id": 10, "player_id": "player_2", "mode": "event", "interactive": True}
    assert not v.validate_move(state, {**base, "event_choices": {"blockade": 4}})
    staged = _start(v, state)
    before = deepcopy(staged)
    assert not v.validate_move(staged, base)
    with pytest.raises(ValueError):
        v.apply_move(staged, base)
    assert staged == before