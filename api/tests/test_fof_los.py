from app.games.fields_of_fire.los import board_los, has_los, los_path
from app.games.fields_of_fire.validator import FieldsOfFireValidator

ROWS, COLS = 3, 4


def _all(colour):
    return lambda _pos: [colour, colour, colour, colour]


def test_path_follows_a_straight_line_and_rejects_knight_moves():
    assert los_path(0, 2, ROWS, COLS) == [0, 1, 2]
    assert los_path(0, 9, ROWS, COLS) is None


def test_adjacent_cards_are_always_in_los_even_behind_dark_borders():
    assert has_los(0, 1, ROWS, COLS, _all("dark")) is True


def test_long_range_needs_white_borders_on_entry_and_exit():
    def borders(pos):
        if pos == 1:
            return ["dark", "white", "dark", "white"]
        return ["white"] * 4
    assert has_los(0, 2, ROWS, COLS, borders) is True


def test_dark_border_on_the_crossed_card_blocks_long_range_los():
    def borders(pos):
        if pos == 1:
            return ["white", "white", "dark", "dark"]
        return ["white"] * 4
    assert has_los(0, 2, ROWS, COLS, borders) is False


def test_very_long_range_is_three_cards_and_no_further():
    assert has_los(0, 3, 1, 5, _all("white")) is True
    assert has_los(0, 4, 1, 5, _all("white")) is False


def test_limited_visibility_only_reaches_adjacent_cards():
    assert has_los(0, 1, ROWS, COLS, _all("white"), limited=True) is True
    assert has_los(0, 2, ROWS, COLS, _all("white"), limited=True) is False


def test_line_must_be_straight_or_diagonal_on_the_grid():
    assert has_los(0, 6, ROWS, COLS, _all("white")) is False


def test_same_card_always_has_los():
    assert has_los(5, 5, ROWS, COLS, _all("dark")) is True


def test_board_los_reads_card_borders_from_the_map():
    # N01 is a hill with dark borders on all sides: blocks a line across it.
    assert board_los(["N01", "N01", "N01"], 1, 3, 0, 2) is False
    assert board_los(["N01", "N01", "N01"], 1, 3, 0, 1) is True


def _vof_state(cards, rows, cols, limited=False):
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["map"]["cards"] = list(cards)
    gd["map"]["rows"] = rows
    gd["map"]["cols"] = cols
    gd["limited_visibility"] = limited
    return v, {"game_data": gd}


def test_vof_without_a_placing_card_keeps_the_position_only_rule():
    v, state = _vof_state(["N01"] * 3, 1, 3)
    assert v.validate_move(state, {"type": "place_vof", "position": 2, "rating": "H"}) is True


def test_vof_from_a_card_out_of_los_is_rejected():
    v, state = _vof_state(["N01"] * 3, 1, 3)
    move = {"type": "place_vof", "position": 2, "rating": "H", "from_position": 0}
    assert v.validate_move(state, move) is False


def test_vof_from_an_adjacent_card_is_accepted():
    v, state = _vof_state(["N01"] * 3, 1, 3)
    move = {"type": "place_vof", "position": 1, "rating": "H", "from_position": 0}
    assert v.validate_move(state, move) is True


def test_vof_from_a_card_with_an_invalid_origin_is_rejected():
    v, state = _vof_state(["N01"] * 3, 1, 3)
    move = {"type": "place_vof", "position": 1, "rating": "H", "from_position": 99}
    assert v.validate_move(state, move) is False
