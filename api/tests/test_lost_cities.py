"""Tests for Lost Cities validator — rules, legal moves, apply, win detection, scoring."""

import pytest

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    COLORS,
    COLOR_SHORT,
    INVESTMENT,
    NUMBERS,
    create_deck,
    parse_card,
    card_color,
    card_value,
    is_investment,
    is_numbered,
    card_number,
    _can_play_to_expedition,
    _calculate_expedition_score,
    _calculate_player_score,
    _initial_game_data,
)


@pytest.fixture
def validator():
    return LostCitiesValidator()


def _make_state(game_data=None, current_player_index=0, players=None):
    if game_data is None:
        game_data = _initial_game_data()
    if players is None:
        players = [
            {"player_id": "player_1", "name": "Human"},
            {"player_id": "player_2", "name": "AI"},
        ]
    return {
        "game_data": game_data,
        "current_player_index": current_player_index,
        "players": players,
    }


# ── Card parsing utilities ────────────────────────────────────────────────

def test_parse_card():
    assert parse_card("b_5") == ("b", "5")
    assert parse_card("r_i") == ("r", "i")
    assert parse_card("g_10") == ("g", "10")


def test_card_color():
    assert card_color("b_5") == "blue"
    assert card_color("y_i") == "yellow"
    assert card_color("r_10") == "red"
    assert card_color("w_2") == "white"
    assert card_color("g_7") == "green"


def test_card_value():
    assert card_value("b_5") == "5"
    assert card_value("r_i") == "i"
    assert card_value("g_10") == "10"


def test_is_investment():
    assert is_investment("b_i") is True
    assert is_investment("r_i") is True
    assert is_investment("b_5") is False
    assert is_investment("g_10") is False


def test_is_numbered():
    assert is_numbered("b_2") is True
    assert is_numbered("r_10") is True
    assert is_numbered("b_i") is False


def test_card_number():
    assert card_number("b_2") == 2
    assert card_number("r_10") == 10
    assert card_number("b_i") is None


def test_create_deck():
    deck = create_deck()
    assert len(deck) == 60
    # Check all cards present
    color_counts = {}
    for card in deck:
        color = card_color(card)
        color_counts[color] = color_counts.get(color, 0) + 1
    for color in COLORS:
        assert color_counts[color] == 12  # 3 investment + 9 numbered


# ── Expedition play legality ──────────────────────────────────────────────

def test_empty_expedition_can_play_investment():
    assert _can_play_to_expedition([], "b_i") is True


def test_empty_expedition_can_play_2():
    assert _can_play_to_expedition([], "b_2") is True


def test_empty_expedition_can_play_any_numbered():
    assert _can_play_to_expedition([], "b_3") is True
    assert _can_play_to_expedition([], "b_10") is True


def test_expedition_with_investment_can_play_2():
    assert _can_play_to_expedition(["b_i"], "b_2") is True


def test_expedition_with_investment_can_play_numbered():
    assert _can_play_to_expedition(["b_i"], "b_3") is True


def test_expedition_with_2_can_play_3():
    assert _can_play_to_expedition(["b_2"], "b_3") is True


def test_expedition_ascending_order():
    exp = ["b_2", "b_5", "b_7"]
    assert _can_play_to_expedition(exp, "b_8") is True
    assert _can_play_to_expedition(exp, "b_7") is False  # not higher
    assert _can_play_to_expedition(exp, "b_6") is False  # not higher


def test_expedition_investment_always_legal():
    exp = ["b_2"]
    assert _can_play_to_expedition(exp, "b_i") is True
    exp = ["b_i", "b_5"]
    assert _can_play_to_expedition(exp, "b_i") is True


def test_expedition_multiple_investments():
    exp = ["b_i", "b_i", "b_i"]
    assert _can_play_to_expedition(exp, "b_2") is True
    assert _can_play_to_expedition(exp, "b_i") is True  # 4th investment not in deck but logically allowed


# ── Scoring ───────────────────────────────────────────────────────────────

def test_score_empty_expedition():
    assert _calculate_expedition_score([]) == 0


def test_score_investment_only():
    # 1 investment: -20 * 2 = -40
    assert _calculate_expedition_score(["b_i"]) == -40
    # 3 investments: -20 * 4 = -80
    assert _calculate_expedition_score(["b_i", "b_i", "b_i"]) == -80


def test_score_numbered_cards():
    # Single 2: (2 - 20) * 1 = -18
    assert _calculate_expedition_score(["b_2"]) == -18
    # 2, 3, 4: (9 - 20) * 1 = -11
    assert _calculate_expedition_score(["b_2", "b_3", "b_4"]) == -11
    # 8, 9, 10: (27 - 20) * 1 = 7
    assert _calculate_expedition_score(["b_8", "b_9", "b_10"]) == 7


def test_score_with_investment_multiplier():
    # 1 investment + 5,6: (11 - 20) * 2 = -18
    assert _calculate_expedition_score(["b_i", "b_5", "b_6"]) == -18
    # 2 investments + 8,9,10: (27 - 20) * 3 = 21
    assert _calculate_expedition_score(["b_i", "b_i", "b_8", "b_9", "b_10"]) == 21


def test_score_length_bonus():
    # 8 cards: base + 20
    cards = ["b_i", "b_i", "b_2", "b_3", "b_4", "b_5", "b_6", "b_7"]  # 8 cards
    base = (2+3+4+5+6+7 - 20) * 3  # (27-20)*3 = 21
    assert _calculate_expedition_score(cards) == base + 20  # 41


def test_score_max_possible():
    # 3 investments + 2-10 (9 cards) = 12 cards, but max 8+ bonus
    # Sum 2-10 = 54, -20 = 34, *4 = 136, +20 = 156
    cards = ["b_i", "b_i", "b_i"] + [f"b_{n}" for n in range(2, 11)]
    assert _calculate_expedition_score(cards) == 156


def test_score_min_possible():
    # 3 investments only: -20 * 4 = -80
    cards = ["b_i", "b_i", "b_i"]
    assert _calculate_expedition_score(cards) == -80


def test_calculate_player_score():
    expeditions = {
        "blue": ["b_5", "b_6", "b_7"],
        "yellow": ["y_i", "y_8", "y_9"],
        "red": [],
        "white": ["w_i", "w_i", "w_2"],
        "green": ["g_10"],
    }
    score = _calculate_player_score(expeditions)
    # blue: (18-20)*1 = -2
    # yellow: (17-20)*2 = -6
    # red: 0
    # white: (2-20)*3 = -54
    # green: (10-20)*1 = -10
    assert score == -2 + -6 + 0 + -54 + -10  # -72


# ── Initial game state ────────────────────────────────────────────────────

def test_initial_game_data_structure():
    data = _initial_game_data()
    assert "player_hands" in data
    assert "expeditions" in data
    assert "discard_piles" in data
    assert "draw_pile" in data
    assert "current_phase" in data
    assert "current_player" in data
    assert "round" in data
    assert "scores" in data
    assert data["current_phase"] == "play_a_card"
    assert data["current_player"] in ("player_1", "player_2")
    assert len(data["player_hands"]["player_1"]) == 8
    assert len(data["player_hands"]["player_2"]) == 8
    assert len(data["draw_pile"]) == 60 - 16  # 44


# ── Validator: get_legal_moves ────────────────────────────────────────────

def test_get_legal_moves_initial_state(validator):
    state = _make_state()
    moves = validator.get_legal_moves(state, "player_1")
    # Should have plays (expedition or discard) for each card in hand
    assert len(moves) > 0
    # All moves should be play_expedition or discard
    for m in moves:
        assert m["type"] in ("play_expedition", "discard")
        assert m["player_id"] == "player_1"


def test_get_legal_moves_only_current_player(validator):
    state = _make_state()
    moves_p1 = validator.get_legal_moves(state, "player_1")
    moves_p2 = validator.get_legal_moves(state, "player_2")
    assert len(moves_p1) > 0
    assert len(moves_p2) == 0  # Not player_2's turn


def test_get_legal_moves_draw_phase(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    game_data["draw_pile"] = ["b_5", "r_3"]
    game_data["discard_piles"]["blue"] = ["b_2"]
    state = _make_state(game_data=game_data)
    moves = validator.get_legal_moves(state, "player_1")
    assert all(m["type"] == "draw" for m in moves)
    sources = {m["source"] for m in moves}
    assert "draw_pile" in sources
    assert "blue_discard" in sources


def test_get_legal_moves_cannot_draw_own_discard(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    game_data["draw_pile"] = ["b_5"]
    game_data["discard_piles"]["blue"] = ["b_3"]
    game_data["last_discarded"] = {"player_id": "player_1", "card": "b_3", "color": "blue"}
    state = _make_state(game_data=game_data)
    moves = validator.get_legal_moves(state, "player_1")
    sources = {m["source"] for m in moves}
    assert "draw_pile" in sources
    assert "blue_discard" not in sources  # Cannot draw own discard


# ── Validator: validate_move ──────────────────────────────────────────────

def test_validate_play_expedition_legal(validator):
    game_data = _initial_game_data()
    # Give player_1 a playable card
    game_data["player_hands"]["player_1"] = ["b_2", "r_i", "y_5"]
    game_data["current_phase"] = "play_a_card"
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "play_expedition", "card": "b_2", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    assert validator.validate_move(state, move) is True


def test_validate_play_expedition_illegal_order(validator):
    game_data = _initial_game_data()
    game_data["player_hands"]["player_1"] = ["b_5"]
    game_data["current_phase"] = "play_a_card"
    game_data["expeditions"]["player_1"]["blue"] = ["b_7"]
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "play_expedition", "card": "b_5", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    assert validator.validate_move(state, move) is False  # Can't play 5 after 7


def test_validate_discard_always_legal(validator):
    game_data = _initial_game_data()
    game_data["player_hands"]["player_1"] = ["b_5"]
    game_data["current_phase"] = "play_a_card"
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "discard", "card": "b_5", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    assert validator.validate_move(state, move) is True


def test_validate_wrong_phase(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "play_expedition", "card": "b_2", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    assert validator.validate_move(state, move) is False


def test_validate_not_current_player(validator):
    game_data = _initial_game_data()
    game_data["current_player"] = "player_2"
    game_data["current_phase"] = "play_a_card"
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "play_expedition", "card": "b_2", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    assert validator.validate_move(state, move) is False


# ── Validator: apply_move ─────────────────────────────────────────────────

def test_apply_play_expedition(validator):
    game_data = _initial_game_data()
    game_data["player_hands"]["player_1"] = ["b_2", "r_3"]
    game_data["current_phase"] = "play_a_card"
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "play_expedition", "card": "b_2", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    
    new_data = new_state["game_data"]
    assert "b_2" in new_data["expeditions"]["player_1"]["blue"]
    assert "b_2" not in new_data["player_hands"]["player_1"]
    assert new_data["current_phase"] == "draw_a_card"
    assert new_data["pending_draw"] is True


def test_apply_discard(validator):
    game_data = _initial_game_data()
    game_data["player_hands"]["player_1"] = ["b_5", "r_3"]
    game_data["current_phase"] = "play_a_card"
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "discard", "card": "b_5", "color": "blue", "hand_index": 0, "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    
    new_data = new_state["game_data"]
    assert new_data["discard_piles"]["blue"] == ["b_5"]
    assert "b_5" not in new_data["player_hands"]["player_1"]
    assert new_data["last_discarded"] == {"player_id": "player_1", "card": "b_5", "color": "blue"}
    assert new_data["current_phase"] == "draw_a_card"
    assert new_data["pending_draw"] is True


def test_apply_draw_from_draw_pile(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    game_data["draw_pile"] = ["b_5", "r_3", "y_7"]
    game_data["pending_draw"] = True
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "draw", "source": "draw_pile", "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    
    new_data = new_state["game_data"]
    assert len(new_data["player_hands"]["player_1"]) == 9  # 8 + 1 drawn
    assert new_data["draw_pile"] == ["r_3", "y_7"]
    assert new_data["current_phase"] == "play_a_card"
    assert new_data["current_player"] == "player_2"
    assert new_data["last_discarded"] is None
    assert new_data["pending_draw"] is False


def test_apply_draw_from_discard(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    game_data["discard_piles"]["blue"] = ["b_2", "b_5"]  # top is b_5
    game_data["pending_draw"] = True
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "draw", "source": "blue_discard", "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    
    new_data = new_state["game_data"]
    assert "b_5" in new_data["player_hands"]["player_1"]
    assert new_data["discard_piles"]["blue"] == ["b_2"]  # top removed


def test_apply_draw_ends_round(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    game_data["draw_pile"] = ["b_5"]  # Last card
    game_data["pending_draw"] = True
    state = _make_state(game_data=game_data)
    
    move = {"move_id": "test", "type": "draw", "source": "draw_pile", "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    
    new_data = new_state["game_data"]
    # Validator immediately starts new round when draw pile exhausted
    assert new_data["round"] == 2  # Round incremented
    assert new_data["round_over"] is False  # New round started
    assert len(new_data["draw_pile"]) == 44  # New deck created (44 cards after dealing 16)


# ── Validator: check_win ──────────────────────────────────────────────────

def test_check_win_not_over(validator):
    state = _make_state()
    assert validator.check_win(state) is None


def test_check_win_game_over(validator):
    game_data = _initial_game_data()
    game_data["game_over"] = True
    game_data["scores"] = {"player_1": 100, "player_2": 50}
    state = _make_state(game_data=game_data)
    
    assert validator.check_win(state) == "player_1"


def test_check_win_game_over_player2(validator):
    game_data = _initial_game_data()
    game_data["game_over"] = True
    game_data["scores"] = {"player_1": 50, "player_2": 100}
    state = _make_state(game_data=game_data)
    
    assert validator.check_win(state) == "player_2"


def test_check_win_tie_goes_to_player1(validator):
    game_data = _initial_game_data()
    game_data["game_over"] = True
    game_data["scores"] = {"player_1": 100, "player_2": 100}
    state = _make_state(game_data=game_data)
    
    assert validator.check_win(state) == "player_1"


# ── Validator: AI ─────────────────────────────────────────────────────────

def test_recommend_ai_move_play_phase(validator):
    game_data = _initial_game_data()
    game_data["player_hands"]["player_2"] = ["b_i", "b_2", "r_5"]
    game_data["current_phase"] = "play_a_card"
    game_data["current_player"] = "player_2"
    state = _make_state(game_data=game_data)
    
    moves = validator.get_legal_moves(state, "player_2")
    ai_move = validator.recommend_ai_move(state, moves)
    
    assert ai_move is not None
    # Should prefer expedition over discard
    assert ai_move["type"] == "play_expedition"


def test_recommend_ai_move_draw_phase(validator):
    game_data = _initial_game_data()
    game_data["current_phase"] = "draw_a_card"
    game_data["draw_pile"] = ["b_5"]
    game_data["discard_piles"]["blue"] = ["b_2"]
    game_data["current_player"] = "player_2"
    state = _make_state(game_data=game_data)
    
    moves = validator.get_legal_moves(state, "player_2")
    ai_move = validator.recommend_ai_move(state, moves)
    
    assert ai_move is not None
    assert ai_move["type"] == "draw"


def test_ai_config(validator):
    config = validator.ai_config()
    assert config is not None
    assert config.iterations > 0
    assert config.exploration_constant > 0
    assert config.max_depth > 0


# ── Validator: serialize_for_screen ───────────────────────────────────────

def test_serialize_for_screen(validator):
    game_data = _initial_game_data()
    serialized = validator.serialize_for_screen(game_data)
    
    assert "player_hands" in serialized
    assert "expeditions" in serialized
    assert "discard_piles" in serialized
    assert "draw_pile" in serialized
    assert serialized["draw_pile"]["count"] == 44
    assert "current_phase" in serialized
    assert "current_player" in serialized
    assert "scores" in serialized


# ── Serialization helpers ─────────────────────────────────────────────────

def test_card_image_path():
    from app.games.lost_cities.serialize import card_image_path, card_back_path, expedition_base_image
    
    assert card_image_path("b_5") == "/api/v1/img/lost_cities/cards/b_5.jpg"
    assert card_image_path("r_i") == "/api/v1/img/lost_cities/cards/r_i.jpg"
    assert card_back_path() == "/api/v1/img/lost_cities/cards/card_backs.jpg"
    assert expedition_base_image("blue") == "/api/v1/img/lost_cities/cards/b_base.jpg"


def test_serialize_hand():
    from app.games.lost_cities.serialize import serialize_hand
    
    hand = ["b_2", "r_i", "g_10"]
    serialized = serialize_hand(hand, is_current_player=True, is_ai=False)
    
    assert len(serialized) == 3
    assert all(c["face_up"] for c in serialized)
    assert serialized[0]["card"] == "b_2"
    assert serialized[1]["is_investment"] is True
    assert serialized[2]["number"] == 10


def test_serialize_hand_ai():
    from app.games.lost_cities.serialize import serialize_hand
    
    hand = ["b_2", "r_i"]
    serialized = serialize_hand(hand, is_current_player=False, is_ai=True)
    
    assert len(serialized) == 2
    assert all(not c["face_up"] for c in serialized)
    assert all(c["image"] == "/api/v1/img/lost_cities/cards/card_backs.jpg" for c in serialized)


def test_serialize_expedition():
    from app.games.lost_cities.serialize import serialize_expedition
    
    cards = ["b_i", "b_5", "b_7"]
    serialized = serialize_expedition(cards)
    
    assert len(serialized) == 3
    assert serialized[0]["is_investment"] is True
    assert serialized[1]["number"] == 5
    assert serialized[2]["number"] == 7


def test_serialize_discard_pile():
    from app.games.lost_cities.serialize import serialize_discard_pile
    
    # Empty
    empty = serialize_discard_pile([])
    assert empty["count"] == 0
    assert empty["top_card"] is None
    
    # With cards
    pile = ["b_2", "b_5", "b_7"]
    serialized = serialize_discard_pile(pile)
    assert serialized["count"] == 3
    assert serialized["top_card"]["card"] == "b_7"
    assert serialized["top_card"]["number"] == 7


def test_serialize_game_data():
    from app.games.lost_cities.serialize import serialize_game_data
    
    game_data = _initial_game_data()
    serialized = serialize_game_data(game_data, "player_1")
    
    assert "player_hands" in serialized
    assert "expeditions" in serialized
    assert "discard_piles" in serialized
    assert "draw_pile" in serialized
    assert serialized["draw_pile"]["count"] == 44


def test_state_response():
    from app.games.lost_cities.serialize import state_response
    
    game_data = _initial_game_data()
    response = state_response(game_data, winner=None, current_player_id="player_1")
    
    assert "game_data" in response
    assert response["winner"] is None
    assert response["current_player_id"] == "player_1"