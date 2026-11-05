"""The purpose-built clone must behave like deepcopy for everything the engine does."""
import json
from copy import deepcopy

import pytest

from app.games.twilight_struggle.state_clone import clone_envelope, clone_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator
from tests.helpers_twilight_replay import fingerprint, initial_state, load_traces

TRACES = load_traces()


def _walk_states():
    validator = TwilightStruggleValidator()
    for trace in TRACES[:4]:
        state = initial_state(validator, trace["seed"])
        yield state
        for move in trace["moves"]:
            state = validator.apply_move(state, move)
            yield state


def test_clone_equals_deepcopy_at_every_step():
    for state in _walk_states():
        gd = state["game_data"]
        assert json.dumps(clone_state(gd), sort_keys=True, default=str) == json.dumps(deepcopy(gd), sort_keys=True, default=str)


def test_clone_is_independent_for_every_engine_style_mutation():
    state = next(iter(_walk_states()))
    gd = state["game_data"]
    before = fingerprint(gd)
    clone = clone_state(gd)

    clone["countries"]["Italy"]["us"] = clone["countries"]["Italy"].get("us", 0) + 5
    clone["tracks"]["defcon"] = 1
    clone["tracks"]["military_operations"]["us"] = 99
    clone.setdefault("persistent_events", {})["nato"] = {"faction": "us"}
    clone["china_card"]["owner"] = "ussr"
    clone["headline_cards"]["us"] = 1
    clone["hands"]["us"].append({"id": 999})
    clone["hands"]["ussr"].clear()
    clone["draw_pile"].pop(0)
    clone["discard_pile"].append({"id": 998})
    clone["removed_cards"].append({"id": 997})
    clone.setdefault("actions_taken", {})["us"] = 7

    assert fingerprint(gd) == before, "mutating the clone changed the original"


def test_unknown_keys_are_deep_copied_by_default():
    gd = {"turn": 1, "brand_new_key": {"nested": [1, 2, {"x": 1}]}}
    clone = clone_state(gd)
    clone["brand_new_key"]["nested"][2]["x"] = 2
    assert gd["brand_new_key"]["nested"][2]["x"] == 1


def test_non_plain_values_fall_back_to_deepcopy_and_are_not_shared():
    gd = {"turn": 1, "weird": {"a_set": {1, 2}, "a_tuple": (1, [2])}}
    clone = clone_state(gd)
    clone["weird"]["a_set"].add(3)
    clone["weird"]["a_tuple"][1].append(9)
    assert gd["weird"]["a_set"] == {1, 2}
    assert gd["weird"]["a_tuple"] == (1, [2])


def test_envelope_clone_keeps_players_rng_and_game_data_independent():
    state = next(iter(_walk_states()))
    clone = clone_envelope(state)
    assert clone["players"] == state["players"] and clone["players"] is not state["players"]
    clone["game_data"]["countries"]["Italy"]["ussr"] = 42
    assert state["game_data"]["countries"]["Italy"].get("ussr") != 42


def test_fast_copy_routes_by_shape_and_never_shares_non_state_objects():
    from app.games.twilight_struggle.state_clone import fast_copy

    state = next(iter(_walk_states()))
    envelope_copy = fast_copy(state)
    assert envelope_copy["game_data"] is not state["game_data"]
    assert fast_copy(state["game_data"])["countries"] is not state["game_data"]["countries"]

    card = {"id": 5, "tags": ["a", "b"]}
    card_copy = fast_copy(card)
    card_copy["tags"].append("c")
    assert card["tags"] == ["a", "b"], "a non-state dict must get a real deepcopy"

    placements = [{"country": "Italy", "amount": 1}]
    assert fast_copy(placements) == placements and fast_copy(placements)[0] is not placements[0]


def test_engine_never_edits_card_records_in_place():
    """Sharing card records between clones is only safe if no code edits a card dict in place."""
    validator = TwilightStruggleValidator()
    for trace in TRACES[:6]:
        state = initial_state(validator, trace["seed"])
        for move in trace["moves"]:
            before = json.dumps(
                [state["game_data"][zone] for zone in ("draw_pile", "discard_pile", "removed_cards", "hands")],
                sort_keys=True, default=str,
            )
            cards_before = {id(card): json.dumps(card, sort_keys=True) for zone in ("draw_pile", "discard_pile", "removed_cards") for card in state["game_data"][zone]}
            cards_before.update({id(card): json.dumps(card, sort_keys=True) for side in state["game_data"]["hands"].values() for card in side})
            new_state = validator.apply_move(state, move)
            for zone in ("draw_pile", "discard_pile", "removed_cards"):
                for card in state["game_data"][zone]:
                    assert json.dumps(card, sort_keys=True) == cards_before[id(card)]
            assert json.dumps(
                [state["game_data"][zone] for zone in ("draw_pile", "discard_pile", "removed_cards", "hands")],
                sort_keys=True, default=str,
            ) == before
            state = new_state
