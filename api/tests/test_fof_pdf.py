import pytest

from app.games.fields_of_fire.pdf import target_card
from app.games.fields_of_fire.validator import FieldsOfFireValidator


def _state(phase="friendly_command"):
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = phase
    gd["map"]["cards"] = ["N01"] * 12  # 3 rows x 4 cols
    return v, {"game_data": gd}


def test_target_card_points_on_the_grid():
    # Card 5 is row 1, col 1 in a 3x4 grid.
    assert target_card(5, "N", rows=3, cols=4) == 9
    assert target_card(5, "S", rows=3, cols=4) == 1
    assert target_card(5, "E", rows=3, cols=4) == 6
    assert target_card(5, "W", rows=3, cols=4) == 4


def test_pdf_pointing_off_the_map_has_no_target():
    assert target_card(0, "S", rows=3, cols=4) is None
    assert target_card(3, "E", rows=3, cols=4) is None


def test_unsupported_direction_is_rejected():
    with pytest.raises(ValueError):
        target_card(5, "NE", rows=3, cols=4)


def test_place_pdf_is_valid_when_it_points_at_a_card_on_the_map():
    v, state = _state()
    assert v.validate_move(state, {"type": "place_pdf", "position": 5, "direction": "N"}) is True


def test_place_pdf_rejects_edges_that_point_off_the_map_and_bad_positions():
    v, state = _state()
    assert v.validate_move(state, {"type": "place_pdf", "position": 0, "direction": "S"}) is False
    assert v.validate_move(state, {"type": "place_pdf", "position": 12, "direction": "N"}) is False
    assert v.validate_move(state, {"type": "place_pdf", "position": 5, "direction": "X"}) is False


def test_place_pdf_stores_its_target_card():
    v, state = _state()
    new_gd = v.apply_move(state, {"type": "place_pdf", "position": 5, "direction": "E"})["game_data"]
    marker = new_gd["pdf_markers"][-1]
    assert marker == {"position": 5, "direction": "E", "target": 6}


def test_place_pdf_is_not_allowed_during_setup():
    v, state = _state(phase="setup")
    assert v.validate_move(state, {"type": "place_pdf", "position": 5, "direction": "N"}) is False


def test_place_pdf_is_no_longer_a_placeholder_legal_move():
    v, state = _state()
    state["players"] = []
    assert [m for m in v.get_legal_moves(state, "player_1") if m["type"] == "place_pdf"] == []
