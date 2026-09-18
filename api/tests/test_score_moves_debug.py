"""Debug score_moves: pass in a board state and see heuristic scores for all moves."""

import pytest

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    COLORS,
    _initial_game_data,
    card_color,
    card_value,
    is_investment,
    is_numbered,
    card_number,
    _get_legal_plays,
    _get_legal_draws,
)


@pytest.fixture
def validator():
    return LostCitiesValidator()


def _make_state(game_data):
    return {
        "game_data": game_data,
        "current_player_index": 0,
        "players": [
            {"player_id": "player_1", "name": "P1"},
            {"player_id": "player_2", "name": "P2"},
        ],
    }


def _print_scores(validator, state, player_id, moves, label=""):
    """Helper to print score_moves results for a list of moves."""
    scores = validator.score_moves(state, player_id, moves)
    print()
    if label:
        print(f"=== {label} ===")
    for m in moves:
        mid = m["move_id"]
        s = scores.get(mid, "MISSING")
        card = m.get("card", "")
        source = m.get("source", "")
        move_type = m.get("type", "")
        if card:
            label_str = f"{card_color(card):>8s}-{card_value(card):>2s}"
        elif source:
            label_str = f"source={source}"
        else:
            label_str = mid
        print(f"  {move_type:20s} {label_str}  -> {s:.2f}")


class TestScoreMovesDebug:
    """Interactive tests to inspect score_moves behavior."""

    def test_turn1_empty_board(self, validator):
        """Turn 1, all expeditions empty, no discards."""
        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_i", "r_3", "b_3", "w_6", "y_i", "y_10"
        ]
        gd["current_player"] = "player_1"
        gd["current_phase"] = "play_a_card"

        state = _make_state(gd)
        moves = _get_legal_plays(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="Turn 1, empty board")

    def test_turn5_mid_game(self, validator):
        """Turn 5, some expeditions started, some discards exist."""
        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_i", "r_3", "b_3", "w_6", "y_i", "y_10"
        ]
        gd["current_player"] = "player_1"
        gd["current_phase"] = "play_a_card"

        # Simulate some expeditions and discards
        gd["expeditions"]["player_1"]["red"] = ["r_i", "r_3"]
        gd["expeditions"]["player_2"]["blue"] = ["b_i", "b_5"]
        gd["discard_piles"]["yellow"] = ["y_2"]
        gd["discard_piles"]["green"] = ["g_10"]

        state = _make_state(gd)
        moves = _get_legal_plays(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="Turn 5, mid game")

    def test_draw_phase(self, validator):
        """Draw phase with discard piles available."""
        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_i", "r_3", "b_3", "w_6", "y_i", "y_10"
        ]
        gd["current_player"] = "player_1"
        gd["current_phase"] = "draw_a_card"
        gd["pending_draw"] = True

        # Some discard piles
        gd["discard_piles"]["yellow"] = ["y_2", "y_8"]
        gd["discard_piles"]["red"] = ["r_4"]

        state = _make_state(gd)
        moves = _get_legal_draws(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="Draw phase with discards")

    def test_unplayable_card_discard(self, validator):
        """A card that cannot be played to any expedition should score higher for discard."""
        gd = _initial_game_data()
        # Player has red expedition going 3, 5, 7 — so 9 can play but 10 cannot yet
        # Actually let's make a case where yellow-10 can't play anywhere
        gd["expeditions"]["player_1"]["yellow"] = ["y_i", "y_5"]
        gd["expeditions"]["player_1"]["red"] = ["r_i", "r_3"]
        gd["expeditions"]["player_1"]["blue"] = ["b_i"]
        gd["expeditions"]["player_1"]["white"] = ["w_i"]
        gd["expeditions"]["player_1"]["green"] = ["g_i"]

        # Yellow already has 5, so yellow-10 CAN play
        # But let's add yellow-7, yellow-8 to make yellow-10 unplayable
        gd["expeditions"]["player_1"]["yellow"] = ["y_i", "y_5", "y_7", "y_8"]

        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_3", "b_3", "w_6", "y_10", "y_4", "g_2"
        ]
        gd["current_player"] = "player_1"
        gd["current_phase"] = "play_a_card"

        state = _make_state(gd)
        moves = _get_legal_plays(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="Yellow-10 unplayable (yellow has 5,7,8)")

    def test_late_game_discard(self, validator):
        """Late game, many cards played, show discard scoring."""
        gd = _initial_game_data()

        # Player 1 expeditions
        gd["expeditions"]["player_1"]["red"] = ["r_i", "r_2", "r_3", "r_5", "r_7"]
        gd["expeditions"]["player_1"]["blue"] = ["b_i", "b_4"]
        gd["expeditions"]["player_1"]["yellow"] = ["y_i"]
        gd["expeditions"]["player_1"]["white"] = []
        gd["expeditions"]["player_1"]["green"] = []

        # Discard piles
        gd["discard_piles"]["red"] = ["r_4"]
        gd["discard_piles"]["blue"] = ["b_2", "b_8"]
        gd["discard_piles"]["green"] = ["g_3"]

        gd["player_hands"]["player_1"] = [
            "r_8", "b_6", "b_9", "w_3", "w_10", "g_5", "g_7", "y_4"
        ]
        gd["current_player"] = "player_1"
        gd["current_phase"] = "play_a_card"

        state = _make_state(gd)
        moves = _get_legal_plays(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="Late game, 8 cards in red expedition")

    def test_all_draw_sources(self, validator):
        """Show scores for all possible draw sources."""
        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_i", "r_3", "b_3", "w_6", "y_i", "y_10"
        ]
        gd["current_player"] = "player_1"
        gd["current_phase"] = "draw_a_card"
        gd["pending_draw"] = True

        # Put some cards in discard piles
        gd["discard_piles"]["yellow"] = ["y_2"]
        gd["discard_piles"]["red"] = ["r_4", "r_6"]
        gd["discard_piles"]["green"] = ["g_10"]

        state = _make_state(gd)
        moves = _get_legal_draws(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="All draw sources")

    def test_compare_discard_scoring(self, validator):
        """Compare discard scores across different card values in same position."""
        gd = _initial_game_data()
        gd["current_player"] = "player_1"
        gd["current_phase"] = "play_a_card"

        # Hand with all 10 values of one color
        gd["player_hands"]["player_1"] = [
            "y_2", "y_3", "y_4", "y_5", "y_6",
            "y_7", "y_8", "y_9", "y_10", "y_i"
        ]

        # Empty yellow expedition so all can play
        state = _make_state(gd)
        moves = _get_legal_plays(state, "player_1")
        _print_scores(validator, state, "player_1", moves,
                       label="All yellow cards, empty expedition")


class TestComputePlayScoreV2:
    """Tests for compute_play_score_v2."""

    def test_blue2_empty_board_no_blue_in_hand(self):
        """User's example: blue-2, empty board, no other blue in hand."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        # Only blue-2 in hand, no other blue cards
        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_i", "r_3", "w_6", "y_i", "y_10", "g_5"
        ]

        score = compute_play_score_v2("b_2", gd["player_hands"]["player_1"], gd)
        print()
        print("=== blue-2, empty board, no other blue in hand ===")
        print(f"  Score: {score:.2f}")
        # guaranteed: b_2 only (no investments for numbered card)
        # Guaranteed score: 2 - 20 = -18
        # To draw: blue-3..blue-10 = 8 numbers
        # Draw sum = 3+4+5+6+7+8+9+10 = 52
        # No investments, multiplier = 1
        # Expected = 52 * 1 * 0.5 = 26
        # Total cards = 1, no bonus (< 8)
        # Total = -18 + 26 + 0 = 8
        assert score == 8.0

    def test_blue2_with_investment(self):
        """blue-2 with blue-i in hand — penalized for wasting investment."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "b_i", "b_2", "r_3", "w_6", "y_i", "y_10", "g_5", "r_9"
        ]

        score = compute_play_score_v2("b_2", gd["player_hands"]["player_1"], gd)
        print()
        print("=== blue-2 with blue-i in hand ===")
        print(f"  Score: {score:.2f}")
        # guaranteed: b_2 only (investments don't count for numbered cards)
        # Guaranteed score: 2 - 20 = -18
        # To draw: blue-3..blue-10 = 8 numbers
        # Draw sum = 52, multiplier = 1
        # Expected = 52 * 0.5 = 26
        # No bonus (< 8 cards)
        # Killed: 0 (no lower blue cards in hand)
        # Wasted investments: 1 * 15 = 15
        # Total = -18 + 26 + 0 - 0 - 15 = -7
        assert score == -7.0

    def test_blue10_empty_board(self):
        """blue-10 on empty board, no other blue in hand."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "b_10", "r_3", "w_6", "y_i", "y_10", "g_5", "r_9", "r_i"
        ]

        score = compute_play_score_v2("b_10", gd["player_hands"]["player_1"], gd)
        print()
        print("=== blue-10, empty board, no other blue in hand ===")
        print(f"  Score: {score:.2f}")
        # guaranteed: b_10 only
        # Guaranteed score: 10 - 20 = -10
        # To draw: nothing higher than 10
        # Expected = 0
        # No bonus (< 8 cards)
        # Total = -10 + 0 + 0 = -10
        assert score == -10.0

    def test_blue5_with_sequential_hand(self):
        """blue-5 with blue-2,3,4,5 in hand — only 5,6,7,8,9,10 count, 2+3+4 killed."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "b_2", "b_3", "b_4", "b_5", "r_9", "w_6", "y_i", "g_5"
        ]

        score = compute_play_score_v2("b_5", gd["player_hands"]["player_1"], gd)
        print()
        print("=== blue-5, with blue-2,3,4,5 in hand ===")
        print(f"  Score: {score:.2f}")
        # guaranteed: b_5 only (b_2,3,4 are lower, killed)
        # Guaranteed score: 5 - 20 = -15
        # To draw: b_6, b_7, b_8, b_9, b_10
        # Draw sum = 6+7+8+9+10 = 40
        # Expected = 40 * 0.5 = 20
        # No bonus (< 8 cards)
        # Killed penalty: (2+3+4) * 3 = 27 (cards in hand lower than 5)
        # No wasted investments (no investments in hand for blue)
        # Total = -15 + 20 + 0 - 27 - 0 = -22
        assert score == -22.0

    def test_blue2_opponent_has_blue3(self):
        """blue-2, opponent has blue-3 in their expedition — skip it."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "b_2", "r_3", "w_6", "y_i", "y_10", "g_5", "r_9", "r_i"
        ]
        gd["expeditions"]["player_2"]["blue"] = ["b_3"]

        score = compute_play_score_v2("b_2", gd["player_hands"]["player_1"], gd)
        print()
        print("=== blue-2, opponent has blue-3 ===")
        print(f"  Score: {score:.2f}")
        # guaranteed: b_2 only
        # Guaranteed score: 2 - 20 = -18
        # To draw: b_4..b_10 (skip b_3 on opponent board)
        # Draw sum = 4+5+6+7+8+9+10 = 49
        # No investments, multiplier = 1
        # Expected = 49 * 0.5 = 24.5
        # No bonus (< 8 cards)
        # Total = -18 + 24.5 + 0 = 6.5
        assert score == 6.5

    def test_six_cards_bonus(self):
        """6 guaranteed cards -> no bonus (need 8+)."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "b_2", "b_3", "b_4", "b_5", "b_6", "b_7", "r_9", "w_6"
        ]

        score = compute_play_score_v2("b_2", gd["player_hands"]["player_1"], gd)
        print()
        print("=== blue-2, 6 blue cards in hand ===")
        print(f"  Score: {score:.2f}")
        # guaranteed_cards = [b_2, b_3, b_4, b_5, b_6, b_7]
        # Guaranteed score: (2+3+4+5+6+7 - 20) * 1 = 7
        # To draw: b_8, b_9, b_10
        # Draw sum = 8+9+10 = 27
        # Expected = 27 * 0.5 = 13.5
        # Total cards = 6, no bonus (< 8)
        # Total = 7 + 13.5 + 0 = 20.5
        assert score == 20.5

    def test_yellow8_with_investments_and_yellow6(self):
        """yellow-8 with 3 investments and yellow-6 — kills yellow-6, wastes investments."""
        from app.games.lost_cities.validator import compute_play_score_v2

        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "y_i", "b_7", "w_3", "y_6", "y_i", "y_8", "w_4", "y_i"
        ]

        score_8 = compute_play_score_v2("y_8", gd["player_hands"]["player_1"], gd)
        score_i = compute_play_score_v2("y_i", gd["player_hands"]["player_1"], gd)
        print()
        print("=== yellow-8 vs yellow-i (3 investments + yellow-6 in hand) ===")
        print(f"  yellow-8: {score_8:.2f}")
        print(f"  yellow-i: {score_i:.2f}")
        # yellow-8:
        #   guaranteed: y_8 only
        #   Guaranteed score: 8 - 20 = -12
        #   To draw: y_9, y_10
        #   Draw sum = 9+10 = 19
        #   Expected = 19 * 0.5 = 9.5
        #   Killed: y_6 = 6 * 3 = 18
        #   Wasted investments: 3 * 15 = 45
        #   Total = -12 + 9.5 + 0 - 18 - 45 = -65.5
        assert score_8 == -65.5
        # yellow-i:
        #   guaranteed: y_i, y_6, y_8 (investments counted, then 6,8 in hand)
        #   Guaranteed score: (6+8-20) * 4 = -24
        #   To draw: y_9, y_10
        #   Draw sum = 9+10 = 19
        #   multiplier = 4 (3 investments + 1)
        #   Expected = 19 * 4 * 0.5 = 38
        #   No killed cards (investment first)
        #   No wasted investments
        #   Total = -24 + 38 + 0 = 14
        assert score_i == 14.0
        # Playing yellow-i should score much higher than yellow-8
        assert score_i > score_8
