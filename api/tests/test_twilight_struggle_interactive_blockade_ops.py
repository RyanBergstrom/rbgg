"""US-owned Blockade Ops and response stages, ordered by the phasing player."""
from copy import deepcopy
import json

import pytest

from app.core.rng import create_rng, serialize_rng
from app.games.twilight_struggle.actions import _server_resolve_random_inputs
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.serialize import serialize_game_state
from tests.test_twilight_struggle_interactive_blockade import CARDS, _state

ORDERS = ("before_operations", "after_operations")


def _setup():
    v, state = _state()
    gd = state["game_data"]
    gd.update(current_player="player_1", current_player_faction="us")
    gd["actions_taken"] = {"us": 0, "ussr": 0}
    gd["hands"] = {"us": [CARDS[10], CARDS[4], CARDS[8]], "ussr": [CARDS[57]]}
    return v, state


def _commit(order, **extra):
    return {"type": "play_card", "player_id": "player_1", "card_id": 10,
            "mode": "operations", "interactive": True, "event_order": order, **extra}


def _response(discard=False):
    return {"type": "event_response", "player_id": "player_1",
            "decision": "discard" if discard else "remove_influence", **({"card_id": 4} if discard else {})}


def _ops(country="W. Germany", points=1):
    return {"type": "card_operations", "player_id": "player_1",
            "operations_action": {"type": "influence", "placements": [{"country": country, "points": points}]}}


def _apply(v, state, move):
    before = deepcopy(state)
    assert v.validate_move(state, move)
    assert state == before
    result = v.apply_move(state, move)
    assert state == before
    assert v.apply_move(json.loads(json.dumps(state)), move) == result
    return result


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("discard", [False, True])
def test_ordered_stages_are_us_owned_persistable_private_and_finish_once(order, discard):
    v, state = _setup()
    staged = _apply(v, state, _commit(order))
    first, second = ((_response(discard), _ops()) if order == "before_operations" else (_ops(), _response(discard)))
    for move in (first, second):
        gd = staged["game_data"]
        assert gd["current_phase"] == move["type"]
        assert gd["current_player"] == "player_1"
        assert gd["current_player_faction"] == "us"
        assert gd["actions_taken"] == {"us": 0, "ussr": 0}
        assert all(c["id"] != 10 for c in gd["hands"]["us"] + gd["removed_cards"] + gd["discard_pile"])
        assert not v.get_legal_moves(staged, "player_2")
        assert not v.validate_move(staged, {**move, "player_id": "player_2"})
        assert not v.validate_move(staged, _commit(order))
        for viewer in ("us", "ussr", None):
            view = serialize_game_state(gd, viewer)
            assert view["pending_event"] == {
                "card_id": 10, "sponsor": "us", "stage": gd["current_phase"],
                "responding_player": "player_1", "mode": "operations", "event_order": order,
            }
            assert "_pending_event" not in view
            assert not {"hands", "rng_state_json", "draw_pile", "eligible_discards", "operations_budget"} & view.keys()
            assert view["hand"] == (gd["hands"][viewer] if viewer else None)
        staged = _apply(v, staged, move)
    gd = staged["game_data"]
    assert "_pending_event" not in gd
    assert gd["actions_taken"] == {"us": 1, "ussr": 0}
    assert gd["current_player"] == "player_2"
    assert gd["removed_cards"][-1]["id"] == 10
    assert gd["countries"]["W. Germany"]["us"] == (5 if discard else (1 if order == "before_operations" else 0))
    assert gd["last_card_play"]["mode"] == "operations"
    assert gd["last_card_play"]["event_triggered"] is True
    assert not v.validate_move(staged, second)


@pytest.mark.parametrize("discard", [False, True])
@pytest.mark.parametrize("action", [_ops(), {"type": "card_operations", "player_id": "player_1",
    "operations_action": {"type": "realignment", "targets": [{"country": "W. Germany", "us_roll": 6, "ussr_roll": 1}]}}])
def test_event_before_ops_is_exactly_legacy_inline_including_server_rng(discard, action):
    v, state = _setup()
    expected = v.apply_move(state, {"type": "play_card", "player_id": "player_1", "card_id": 10,
        "mode": "operations", "event_choices": {"blockade": 4} if discard else {},
        "operations_action": action["operations_action"]})
    staged = _apply(v, state, _commit("before_operations"))
    staged = _apply(v, staged, _response(discard))
    assert _apply(v, staged, action) == expected


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("modifier,budget", [(None, 1), ("containment", 2), ("red_scare_purge", 1), ("expired", 1)])
def test_us_modified_budget_and_private_discard_eligibility(order, modifier, budget):
    v, state = _setup()
    gd = state["game_data"]
    if modifier:
        name = "containment" if modifier == "expired" else modifier
        gd["persistent_events"][name] = {"faction": "us", "expires_turn": 0 if modifier == "expired" else 1}
    # An opponent's boost must not increase the phasing US Ops budget.
    gd["persistent_events"]["brezhnev_doctrine"] = {"faction": "ussr", "expires_turn": 1}
    staged = _apply(v, state, _commit(order))
    if order == "before_operations":
        ids = {m.get("card_id") for m in v.get_legal_moves(staged, "player_1")}
        assert (4 in ids) == (modifier != "red_scare_purge")
        assert (8 in ids) == (modifier == "containment")
        staged = _apply(v, staged, _response())
    before = deepcopy(staged)
    assert not v.validate_move(staged, _ops(points=budget + 1))
    with pytest.raises(ValueError):
        v.apply_move(staged, _ops(points=budget + 1))
    assert staged == before
    result = _apply(v, staged, _ops(points=budget))
    assert result["game_data"]["operations_spent"] == budget
    if order == "after_operations":
        result = _apply(v, result, _response())
    assert result["game_data"]["actions_taken"]["us"] == 1


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("seed,success", [(1, True), (5, False)])
def test_restriction_gate_spends_discard_and_rng_only_once(order, seed, success):
    v, state = _setup()
    gd = state["game_data"]
    gd.update(rng_seed=seed, rng_state_json="{}")
    gd["persistent_events"]["action_restriction"] = {"faction": "us"}
    staged = _apply(v, state, _commit(order, restriction_discard_id=8))
    rng = create_rng(seed, "{}")
    rng.randint(1, 6)
    expected_rng = serialize_rng(rng)
    assert staged["game_data"]["rng_state_json"] == expected_rng
    if success:
        moves = (_response(True), _ops()) if order == "before_operations" else (_ops(), _response(True))
        for move in moves:
            staged = _apply(v, staged, move)
        assert [c["id"] for c in staged["game_data"]["discard_pile"]] == [8, 4]
        assert staged["game_data"]["last_card_play"]["mode"] == "operations"
    else:
        assert "_pending_event" not in staged["game_data"]
        assert any(c["id"] == 10 for c in staged["game_data"]["hands"]["us"])
        assert staged["game_data"]["countries"] == gd["countries"]
    assert staged["game_data"]["actions_taken"]["us"] == 1
    assert staged["game_data"]["rng_state_json"] == expected_rng


@pytest.mark.parametrize("order", ORDERS)
def test_winning_pre_card_penalty_preempts_commit_and_both_stages(order):
    v, state = _setup()
    gd = state["game_data"]
    gd["tracks"]["victory_points"] = -18
    gd["persistent_events"]["we_will_bury_you"] = {"faction": "ussr"}
    after = _apply(v, state, _commit(order))["game_data"]
    assert after["current_phase"] == "game_over"
    assert after["terminal_result"] == {"winner": "ussr", "reason": "twenty_vp"}
    assert after["hands"] == gd["hands"]
    assert after["countries"] == gd["countries"]
    assert after["rng_state_json"] == gd["rng_state_json"]
    assert "_pending_event" not in after


def test_terminal_ops_preempts_later_event_and_discards_untriggered_blockade():
    v, state = _setup()
    gd = state["game_data"]
    gd["persistent_events"]["cuban_missile_crisis"] = {"faction": "us", "expires_turn": 1}
    gd["countries"]["Cuba"] = {"us": 0, "ussr": 3}
    staged = _apply(v, state, _commit("after_operations"))
    move = {"type": "card_operations", "player_id": "player_1",
            "operations_action": {"type": "coup", "country": "Cuba", "die_roll": 6}}
    after = _apply(v, staged, move)["game_data"]
    assert after["current_phase"] == "game_over"
    assert after["countries"] == gd["countries"]
    assert after["terminal_result"] == {"winner": "ussr", "reason": "cuban_missile_crisis"}
    assert after["discard_pile"][-1]["id"] == 10
    assert not after["removed_cards"]
    assert after["last_card_play"]["event_triggered"] is False
    assert after["actions_taken"]["us"] == 1
    assert "_pending_event" not in after


def test_ops_after_event_are_chosen_fresh_on_post_blockade_board():
    v, state = _setup()
    gd = state["game_data"]
    # An influence anchor in W. Germany is removed before the Ops decision.
    gd["countries"] = {name: {"us": 0, "ussr": 0} for name in gd["countries"]}
    gd["countries"]["W. Germany"]["us"] = 4
    staged = _apply(v, state, _commit("before_operations"))
    staged = _apply(v, staged, _response())
    assert not v.validate_move(staged, _ops("France"))
    # Canada remains legal via direct superpower adjacency even after the anchor is lost.
    assert v.validate_move(staged, _ops("Canada"))


@pytest.mark.parametrize("order", [None, "before", "", True, 1, [], {}])
def test_missing_or_malformed_order_is_atomic(order):
    v, state = _setup()
    move = _commit(order)
    if order is None:
        del move["event_order"]
    before = deepcopy(state)
    assert not v.validate_move(state, move)
    with pytest.raises(ValueError):
        v.apply_move(state, move)
    assert state == before


@pytest.mark.parametrize("extra", [
    {"operations_action": _ops()["operations_action"]}, {"event_choices": {"blockade": 4}},
    {"trigger_own_event": True}, {"chosen_defcon": 2}, {"mode": "event"},
    {"card_id": 20}, {"interactive": False}, {"player_id": "player_2"},
])
def test_order_and_inline_payload_misuse_at_commit_is_rejected(extra):
    v, state = _setup()
    move = _commit("before_operations", **extra)
    before = deepcopy(state)
    assert not v.validate_move(state, move)
    with pytest.raises(ValueError):
        v.apply_move(state, move)
    assert state == before


def test_order_on_legacy_inline_move_is_rejected_not_silently_ignored():
    v, state = _setup()
    move = _commit("after_operations", operations_action=_ops()["operations_action"])
    del move["interactive"]
    assert not v.validate_move(state, move)
    with pytest.raises(ValueError):
        v.apply_move(state, move)


@pytest.mark.parametrize("extra", [
    {"player_id": "player_2"}, {"event_order": "after_operations"}, {"operations": 4},
    {"decline": True}, {"event_choices": {"blockade": 4}}, {"card_id": 57},
    {"operations_action": {"type": "space_race"}}, {"operations_action": None},
])
def test_ops_stage_rejects_wrong_owner_or_injected_payload_atomically(extra):
    v, state = _setup()
    staged = _apply(v, state, _commit("after_operations"))
    move = {**_ops(), **extra}
    before = deepcopy(staged)
    assert not v.validate_move(staged, move)
    with pytest.raises(ValueError):
        v.apply_move(staged, move)
    assert staged == before


def test_wrong_stage_types_and_repeat_ops_are_rejected():
    v, state = _setup()
    staged = _apply(v, state, _commit("after_operations"))
    assert not v.validate_move(staged, _response())
    assert not v.validate_move(staged, {"type": "event_bonus", "player_id": "player_1", "decline": True})
    staged = _apply(v, staged, _ops())
    assert not v.validate_move(staged, _ops())
    assert not v.validate_move(staged, {**_response(), "event_order": "before_operations"})


def test_legal_templates_are_faction_specific_and_ops_template_requires_payload():
    v, state = _setup()
    assert next(m for m in v.get_legal_moves(state, "player_1") if m.get("card_id") == 10)["interactive_modes"] == ["operations"]
    staged = _apply(v, state, _commit("after_operations"))
    template, = v.get_legal_moves(staged, "player_1")
    assert template == {"type": "card_operations", "player_id": "player_1"}
    assert not v.validate_move(staged, template)


def test_ops_first_server_roll_and_board_match_pure_operations_before_response():
    v, state = _setup()
    staged = _apply(v, state, _commit("after_operations"))
    gd = staged["game_data"]
    rng = create_rng(gd["rng_seed"], gd["rng_state_json"])
    action = {"type": "realignment", "targets": [{"country": "W. Germany", "us_roll": 99, "ussr_roll": 99}]}
    expected = resolve_operations_action(gd, "us", 1, _server_resolve_random_inputs(action, rng))
    result = _apply(v, staged, {"type": "card_operations", "player_id": "player_1", "operations_action": action})
    assert result["game_data"]["countries"] == expected["countries"]
    assert result["game_data"]["last_ops_result"] == expected["last_ops_result"]
    assert result["game_data"]["rng_state_json"] == serialize_rng(rng)
    assert result["rng_state_json"] == serialize_rng(rng)


@pytest.mark.parametrize("order", ORDERS)
def test_terminal_event_preempts_later_ops_and_keeps_completed_ops(order, monkeypatch):
    # Blockade itself changes no VP/DEFCON tracks. Inject a terminal handler result
    # to exercise the shared stage boundary without inventing a Blockade rule.
    from app.games.twilight_struggle import interaction

    original = interaction.resolve_card_event

    def terminal_event(*args, **kwargs):
        result = original(*args, **kwargs)
        result["terminal_result"] = {"winner": "us", "reason": "twenty_vp"}
        result["game_data"]["tracks"]["victory_points"] = 20
        result["game_data"]["terminal_result"] = result["terminal_result"]
        return result

    monkeypatch.setattr(interaction, "resolve_card_event", terminal_event)
    v, state = _setup()
    staged = _apply(v, state, _commit(order))
    if order == "after_operations":
        staged = _apply(v, staged, _ops("Canada"))
    before = deepcopy(staged["game_data"])
    after = _apply(v, staged, _response(True))
    gd = after["game_data"]
    assert gd["current_phase"] == "game_over"
    assert gd["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert gd["countries"] == before["countries"]
    assert gd["rng_state_json"] == before["rng_state_json"]
    assert gd["actions_taken"] == {"us": 1, "ussr": 0}
    assert gd["removed_cards"][-1]["id"] == 10
    assert "_pending_event" not in gd
    assert not v.get_legal_moves(after, "player_1")
    assert not v.validate_move(after, _ops())


@pytest.mark.parametrize("order", ORDERS)
def test_live_ops_nuclear_loss_removes_card_only_if_event_already_happened(order):
    v, state = _setup()
    gd = state["game_data"]
    gd["tracks"]["defcon"] = 2
    gd["countries"]["Cuba"] = {"us": 0, "ussr": 3}
    staged = _apply(v, state, _commit(order))
    if order == "before_operations":
        staged = _apply(v, staged, _response(True))
    result = _apply(v, staged, {"type": "card_operations", "player_id": "player_1",
        "operations_action": {"type": "coup", "country": "Cuba"}})["game_data"]
    assert result["current_phase"] == "game_over"
    assert result["terminal_result"] == {"winner": "ussr", "reason": "defcon_1"}
    assert result["last_card_play"]["event_triggered"] == (order == "before_operations")
    zone = "removed_cards" if order == "before_operations" else "discard_pile"
    assert result[zone][-1]["id"] == 10
    assert result["actions_taken"]["us"] == 1
    if order == "after_operations":
        assert result["countries"]["W. Germany"] == gd["countries"]["W. Germany"]


@pytest.mark.parametrize("order", ORDERS)
def test_last_action_closes_turn_only_after_both_stages(order):
    v, state = _setup()
    gd = state["game_data"]
    gd["hands"] = {"us": [CARDS[10], CARDS[4]], "ussr": []}
    gd["actions_taken"] = {"us": 5, "ussr": 6}
    staged = _apply(v, state, _commit(order))
    moves = (_response(True), _ops()) if order == "before_operations" else (_ops(), _response(True))
    staged = _apply(v, staged, moves[0])
    assert staged["game_data"]["actions_taken"] == {"us": 5, "ussr": 6}
    assert staged["game_data"]["current_phase"] in {"event_response", "card_operations"}
    result = _apply(v, staged, moves[1])["game_data"]
    assert result["current_phase"] == "turn_end"
    assert result["actions_taken"] == {"us": 6, "ussr": 6}
    assert result["hands"] == {"us": [], "ussr": []}


def test_norad_waits_for_ops_first_blockade_response_then_applies_once():
    v, state = _setup()
    gd = state["game_data"]
    gd["tracks"]["defcon"] = 3
    gd["countries"]["Canada"]["us"] = 5
    gd["countries"]["Cuba"] = {"us": 0, "ussr": 3}
    gd["persistent_events"]["norad"] = {"faction": "us"}
    staged = _apply(v, state, _commit("after_operations"))
    staged = _apply(v, staged, {"type": "card_operations", "player_id": "player_1",
        "operations_action": {"type": "coup", "country": "Cuba"}})
    assert staged["game_data"]["tracks"]["defcon"] == 2
    target = sorted(n for n, inf in staged["game_data"]["countries"].items() if inf["us"] > 0)[0]
    before = deepcopy(staged["game_data"]["countries"])
    assert before[target] == gd["countries"][target]
    result = _apply(v, staged, _response(True))["game_data"]
    before[target]["us"] += 1
    assert result["countries"] == before


@pytest.mark.parametrize("order", ORDERS)
def test_nonterminal_pre_card_penalty_runs_once_not_on_each_stage(order):
    v, state = _setup()
    state["game_data"]["persistent_events"]["we_will_bury_you"] = {"faction": "ussr"}
    staged = _apply(v, state, _commit(order))
    expected = state["game_data"]["tracks"]["victory_points"] - 3
    assert staged["game_data"]["tracks"]["victory_points"] == expected
    moves = (_response(True), _ops()) if order == "before_operations" else (_ops(), _response(True))
    for move in moves:
        staged = _apply(v, staged, move)
        assert staged["game_data"]["tracks"]["victory_points"] == expected


@pytest.mark.parametrize("order", ORDERS)
def test_empty_remaining_hand_can_complete_response_and_ops(order):
    v, state = _setup()
    state["game_data"]["hands"]["us"] = [CARDS[10]]
    staged = _apply(v, state, _commit(order))
    moves = (_response(), _ops()) if order == "before_operations" else (_ops(), _response())
    for move in moves:
        staged = _apply(v, staged, move)
    assert staged["game_data"]["actions_taken"]["us"] == 1
    assert staged["game_data"]["removed_cards"][-1]["id"] == 10


def test_crisis_payment_between_stages_preserves_order_budget_and_does_not_repeat_ops():
    v, state = _setup()
    gd = state["game_data"]
    gd["persistent_events"]["containment"] = {"faction": "us", "expires_turn": 1}
    gd["persistent_events"]["cuban_missile_crisis"] = {"faction": "us", "expires_turn": 1}
    gd["countries"]["Turkey"]["us"] = 2
    gd["countries"]["Cuba"] = {"us": 0, "ussr": 3}
    staged = _apply(v, state, _commit("before_operations"))
    staged = _apply(v, staged, _response(True))
    pending = deepcopy(staged["game_data"]["_pending_event"])
    cancellation = next(m for m in v.get_legal_moves(staged, "player_1") if m.get("country") == "Turkey")
    staged = _apply(v, staged, cancellation)
    assert staged["game_data"]["_pending_event"] == pending
    assert pending["operations_budget"] == 2
    result = _apply(v, staged, {"type": "card_operations", "player_id": "player_1",
        "operations_action": {"type": "coup", "country": "Cuba"}})["game_data"]
    assert result.get("terminal_result") is None
    assert result["tracks"]["military_operations"]["us"] == 2
    assert result["countries"]["Turkey"]["us"] == 0
    assert result["actions_taken"]["us"] == 1


@pytest.mark.parametrize("counts", [{"us": 6, "ussr": 5}, {"us": 7, "ussr": 7}])
def test_no_ops_commit_after_us_action_limit(counts):
    v, state = _setup()
    state["game_data"]["actions_taken"] = counts
    assert not v.validate_move(state, _commit("before_operations"))
    with pytest.raises(ValueError):
        v.apply_move(state, _commit("before_operations"))