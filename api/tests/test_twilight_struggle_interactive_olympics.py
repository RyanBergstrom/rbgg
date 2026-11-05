"""An opt-in Olympic event pauses for the opponent, then the sponsor's own Ops."""
from copy import deepcopy
import json

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {c["id"]: c for c in load_standard_card_catalog()}


def _state(sponsor="us", defcon=5):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5)
    gd["current_phase"] = "action_round"
    gd["current_player_faction"] = sponsor
    gd["current_player"] = gd["player_by_faction"][sponsor]
    gd["tracks"]["defcon"] = defcon
    gd["hands"] = {"us": [CARDS[4]], "ussr": [CARDS[8]]}
    gd["hands"][sponsor] = [CARDS[20], CARDS[57]]
    return validator, {"game_data": gd}


def _begin(validator, state):
    move = {"type": "play_card", "player_id": state["game_data"]["current_player"],
            "card_id": 20, "mode": "event", "interactive": True}
    assert validator.validate_move(state, move)
    return validator.apply_move(state, move)


def _response(validator, state, decision):
    move = {"type": "event_response", "player_id": state["game_data"]["current_player"], "decision": decision}
    assert validator.validate_move(state, move)
    return validator.apply_move(state, move)


@pytest.mark.parametrize("sponsor", ["us", "ussr"])
def test_commit_card_then_only_opponent_can_respond(sponsor):
    validator, state = _state(sponsor)
    before = deepcopy(state)
    staged = _begin(validator, state)
    gd = staged["game_data"]
    other = "ussr" if sponsor == "us" else "us"
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == gd["player_by_faction"][other]
    assert [c["id"] for c in gd["hands"][sponsor]] == [57]
    assert gd.get("actions_taken", {}).get(sponsor, 0) == 0
    assert gd["rng_state_json"] == before["game_data"]["rng_state_json"]
    assert state == before
    moves = validator.get_legal_moves(staged, gd["current_player"])
    assert {m["decision"] for m in moves} == {"participate", "boycott"}
    assert validator.get_legal_moves(staged, gd["player_by_faction"][sponsor]) == []
    assert not validator.validate_move(staged, {**moves[0], "player_id": gd["player_by_faction"][sponsor]})


def test_participation_finishes_one_action_and_matches_inline_event():
    validator, state = _state()
    inline = {"type": "play_card", "player_id": "player_1", "card_id": 20, "mode": "event",
              "event_choices": {"olympic_games": "participate"}}
    expected = validator.apply_move(state, inline)
    after = _response(validator, _begin(validator, state), "participate")
    assert after == expected
    assert after["game_data"]["actions_taken"] == {"us": 1, "ussr": 0}
    assert after["game_data"]["discard_pile"][-1]["id"] == 20


def test_boycott_applies_defcon_before_sponsor_decides_bonus():
    validator, state = _state()
    staged = _begin(validator, state)
    rng_before = staged["game_data"]["rng_state_json"]
    after = _response(validator, staged, "boycott")
    gd = after["game_data"]
    assert gd["tracks"]["defcon"] == 4
    assert gd["current_phase"] == "event_bonus"
    assert gd["current_player"] == "player_1"
    assert gd.get("actions_taken", {}).get("us", 0) == 0
    assert gd["rng_state_json"] == rng_before
    assert validator.get_legal_moves(after, "player_2") == []


@pytest.mark.parametrize("decline", [True, False])
def test_sponsor_bonus_or_decline_matches_inline_and_costs_one_action(decline):
    validator, state = _state()
    state["game_data"]["countries"]["France"]["us"] = 1
    action = {"type": "influence", "placements": [{"country": "France", "points": 4}]}
    choices = {"olympic_games": "boycott"}
    if not decline:
        choices["bonus_operations"] = action
    expected = validator.apply_move(state, {"type": "play_card", "player_id": "player_1", "card_id": 20,
                                           "mode": "event", "event_choices": choices})
    staged = _response(validator, _begin(validator, state), "boycott")
    move = {"type": "event_bonus", "player_id": "player_1", "decline": decline}
    if not decline:
        move["operations_action"] = action
    assert validator.validate_move(staged, move)
    after = validator.apply_move(staged, move)
    assert after == expected
    assert after["game_data"]["countries"]["France"]["us"] == (1 if decline else 5)
    assert not validator.validate_move(after, move)


def test_boycott_nuclear_loss_never_offers_bonus_or_advances_another_turn():
    validator, state = _state(defcon=2)
    after = _response(validator, _begin(validator, state), "boycott")
    assert after["game_data"]["current_phase"] == "game_over"
    assert after["game_data"]["terminal_result"] == {"winner": "ussr", "reason": "defcon_1"}
    assert after["game_data"]["actions_taken"]["us"] == 1
    assert "_pending_event" not in after["game_data"]
    assert not validator.get_legal_moves(after, "player_1")


@pytest.mark.parametrize("stage", ["response", "bonus"])
def test_pending_state_is_json_persistable_and_projects_only_public_choice(stage):
    validator, state = _state()
    staged = _begin(validator, state)
    if stage == "bonus":
        staged = _response(validator, staged, "boycott")
    restored = json.loads(json.dumps(staged))
    for viewer in ("us", "ussr", None):
        view = serialize_game_state(restored["game_data"], viewer)
        assert "_pending_event" not in view
        assert view["pending_event"]["card_id"] == 20
        assert view["pending_event"]["sponsor"] == "us"
        assert not {"hands", "draw_pile", "headline_cards", "rng_state_json"} & view.keys()
    move = ({"type": "event_response", "decision": "participate", "player_id": "player_2"} if stage == "response" else
            {"type": "event_bonus", "player_id": "player_1", "decline": True})
    assert validator.apply_move(restored, move) == validator.apply_move(staged, move)


@pytest.mark.parametrize("bad", ["owner", "choice", "inject_bonus", "inject_dice"])
def test_response_rejects_spoofed_actor_or_payload_atomically(bad):
    validator, state = _state()
    staged = _begin(validator, state)
    move = {"type": "event_response", "player_id": "player_2", "decision": "participate"}
    if bad == "owner":
        move["player_id"] = "player_1"
    elif bad == "choice":
        move["decision"] = "win"
    elif bad == "inject_bonus":
        move["operations_action"] = {"type": "influence", "placements": []}
    else:
        move["die_roll"] = 6
    before = deepcopy(staged)
    assert not validator.validate_move(staged, move)
    with pytest.raises(ValueError):
        validator.apply_move(staged, move)
    assert staged == before


def test_bonus_overspending_and_opponent_submissions_fail_without_consuming_rng():
    validator, state = _state()
    staged = _response(validator, _begin(validator, state), "boycott")
    move = {"type": "event_bonus", "player_id": "player_1", "decline": False,
            "operations_action": {"type": "influence", "placements": [{"country": "France", "points": 5}]}}
    before = deepcopy(staged)
    assert not validator.validate_move(staged, move)
    with pytest.raises(ValueError):
        validator.apply_move(staged, move)
    assert not validator.validate_move(staged, {"type": "event_bonus", "player_id": "player_2", "decline": True})
    assert staged == before


def test_staging_rejects_inline_choice_injection_and_unsupported_ops_mode():
    validator, state = _state()
    base = {"type": "play_card", "player_id": "player_1", "card_id": 20, "mode": "event", "interactive": True}
    assert not validator.validate_move(state, {**base, "event_choices": {"olympic_games": "boycott"}})
    assert not validator.validate_move(state, {**base, "mode": "operations", "operations_action": {"type": "influence", "placements": []}})
    assert not validator.validate_move(state, {**base, "card_id": 57})


def test_legal_card_template_advertises_only_supported_interactive_mode():
    validator, state = _state()
    moves = validator.get_legal_moves(state, "player_1")
    olympic = next(m for m in moves if m.get("card_id") == 20)
    assert olympic["interactive_modes"] == ["event"]
    assert "interactive_modes" not in next(m for m in moves if m.get("card_id") == 57)


def test_cannot_play_another_card_while_waiting_for_opponent():
    validator, state = _state()
    staged = _begin(validator, state)
    move = {"type": "play_card", "player_id": "player_1", "card_id": 57, "mode": "event"}
    assert not validator.validate_move(staged, move)
    with pytest.raises(ValueError, match="pending"):
        validator.apply_move(staged, move)


def test_response_participation_victory_ends_before_any_bonus():
    validator, state = _state()
    state["game_data"]["tracks"]["victory_points"] = 19
    state["game_data"]["rng_seed"] = 0
    state["game_data"]["rng_state_json"] = "{}"
    result = _response(validator, _begin(validator, state), "participate")
    assert result["game_data"]["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert result["game_data"]["current_phase"] == "game_over"
    assert result["game_data"]["actions_taken"]["us"] == 1


@pytest.mark.parametrize("success,seed", [(True, 1), (False, 5)])
def test_restriction_gate_runs_once_before_opponent_choice(success, seed):
    validator, state = _state()
    gd = state["game_data"]
    gd["rng_seed"], gd["rng_state_json"] = seed, "{}"
    gd["persistent_events"]["action_restriction"] = {"faction": "us"}
    move = {"type": "play_card", "player_id": "player_1", "card_id": 20, "mode": "event",
            "interactive": True, "restriction_discard_id": 57}
    assert validator.validate_move(state, move)
    staged = validator.apply_move(state, move)
    assert staged["game_data"]["discard_pile"][-1]["id"] == 57
    if success:
        assert staged["game_data"]["current_phase"] == "event_response"
        assert "action_restriction" not in staged["game_data"]["persistent_events"]
        completed = _response(validator, staged, "participate")
        assert completed["game_data"]["actions_taken"]["us"] == 1
        assert [c["id"] for c in completed["game_data"]["discard_pile"]].count(57) == 1
    else:
        assert "_pending_event" not in staged["game_data"]
        assert any(c["id"] == 20 for c in staged["game_data"]["hands"]["us"])
        assert staged["game_data"]["actions_taken"]["us"] == 1


def test_winning_penalty_ends_before_commit_or_response():
    validator, state = _state()
    gd = state["game_data"]
    gd["tracks"]["victory_points"] = -18
    gd["persistent_events"]["we_will_bury_you"] = {"faction": "ussr"}
    result = _begin(validator, state)
    assert result["game_data"]["current_phase"] == "game_over"
    assert result["game_data"]["terminal_result"] == {"winner": "ussr", "reason": "twenty_vp"}
    assert any(c["id"] == 20 for c in result["game_data"]["hands"]["us"])
    assert "_pending_event" not in result["game_data"]


def test_crisis_cancellation_can_interrupt_between_response_and_bonus_not_replay_event():
    validator, state = _state()
    gd = state["game_data"]
    gd["persistent_events"]["cuban_missile_crisis"] = {"faction": "us", "expires_turn": gd["turn"]}
    gd["countries"]["Turkey"]["us"] = 2
    staged = _response(validator, _begin(validator, state), "boycott")
    cancellation = next(m for m in validator.get_legal_moves(staged, "player_1")
                        if m["type"] == "cancel_cuban_missile_crisis" and m["country"] == "Turkey")
    paid = validator.apply_move(staged, cancellation)
    assert paid["game_data"]["current_phase"] == "event_bonus"
    assert paid["game_data"]["countries"]["Turkey"]["us"] == 0
    finished = validator.apply_move(paid, {"type": "event_bonus", "player_id": "player_1", "decline": True})
    assert finished["game_data"]["tracks"]["defcon"] == 4
    assert finished["game_data"]["countries"]["Turkey"]["us"] == 0


def test_norad_round_end_waits_until_bonus_decision_and_matches_inline():
    validator, state = _state(defcon=3)
    gd = state["game_data"]
    gd["countries"]["Canada"]["us"] = 5
    gd["persistent_events"]["norad"] = {"faction": "us"}
    staged = _response(validator, _begin(validator, state), "boycott")
    assert staged["game_data"]["countries"] == gd["countries"]
    expected = validator.apply_move(state, {"type": "play_card", "player_id": "player_1", "card_id": 20,
                                           "mode": "event", "event_choices": {"olympic_games": "boycott"}})
    after = validator.apply_move(staged, {"type": "event_bonus", "player_id": "player_1", "decline": True})
    assert after == expected
    assert after["game_data"]["countries"] != gd["countries"]