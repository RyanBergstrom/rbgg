import pytest

from app.games.fields_of_fire.validator import FieldsOfFireValidator
from app.games.fields_of_fire.vof import best_vof, vof_value


def _state(phase="friendly_command"):
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = phase
    gd["map"]["cards"] = ["N01"] * 12
    return v, {"game_data": gd}


def test_rulebook_values_for_basic_ratings():
    assert vof_value("S") == 0
    assert vof_value("A") == -1
    assert vof_value("H") == -3
    assert vof_value("PINNED") == 2


def test_automatic_small_arms_depends_on_range():
    assert vof_value("A/S", point_blank=True) == -1
    assert vof_value("A/S", point_blank=False) == 0


def test_unsupported_rating_has_no_value():
    with pytest.raises(ValueError):
        vof_value("G!")


def test_place_vof_is_valid_on_a_board_card_and_stores_its_value():
    v, state = _state()
    move = {"type": "place_vof", "position": 4, "rating": "H"}
    assert v.validate_move(state, move) is True
    new_gd = v.apply_move(state, move)["game_data"]
    marker = new_gd["vof_markers"][-1]
    assert marker["position"] == 4
    assert marker["rating"] == "H"
    assert marker["value"] == -3


def test_place_vof_records_point_blank_for_automatic_small_arms():
    v, state = _state()
    move = {"type": "place_vof", "position": 2, "rating": "A/S", "point_blank": True}
    new_gd = v.apply_move(state, move)["game_data"]
    assert new_gd["vof_markers"][-1]["value"] == -1


def test_place_vof_rejects_unsupported_rating_and_off_board_position():
    v, state = _state()
    assert v.validate_move(state, {"type": "place_vof", "position": 0, "rating": "WP"}) is False
    assert v.validate_move(state, {"type": "place_vof", "position": -1, "rating": "A"}) is False
    assert v.validate_move(state, {"type": "place_vof", "position": 12, "rating": "A"}) is False


def test_place_vof_is_not_allowed_during_setup():
    v, state = _state(phase="setup")
    assert v.validate_move(state, {"type": "place_vof", "position": 0, "rating": "A"}) is False


def test_best_vof_is_the_lowest_value_on_that_card():
    markers = [
        {"position": 3, "rating": "S", "value": 0},
        {"position": 3, "rating": "H", "value": -3},
        {"position": 3, "rating": "PINNED", "value": 2},
        {"position": 7, "rating": "A", "value": -1},
    ]
    assert best_vof(markers, 3)["rating"] == "H"
    assert best_vof(markers, 7)["rating"] == "A"
    assert best_vof(markers, 9) is None


def test_best_vof_ignores_legacy_markers_without_a_value():
    # open_fire still writes markers without a value; they must not count.
    markers = [{"position": 1, "rating": "A"}, {"position": 1, "rating": "S", "value": 0}]
    assert best_vof(markers, 1)["rating"] == "S"


def test_place_vof_is_no_longer_a_placeholder_legal_move():
    v, state = _state()
    state["players"] = []
    assert [m for m in v.get_legal_moves(state, "player_1") if m["type"] == "place_vof"] == []
