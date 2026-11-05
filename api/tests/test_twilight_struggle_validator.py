from app.games.twilight_struggle.cards import standard_deck
from app.games.twilight_struggle.validator import TwilightStruggleValidator


def test_initial_state_maps_players_to_factions_and_exposes_ussr_headline():
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(23, ["alice", "bob"])
    state = {"players": [{"player_id": "alice"}, {"player_id": "bob"}], "game_data": game_data}

    assert game_data["player_by_faction"] == {"us": "alice", "ussr": "bob"}
    moves = validator.get_legal_moves(state, "bob")
    assert moves
    assert all(move["type"] == "headline" for move in moves)
    assert validator.get_legal_moves(state, "alice")


def test_headline_submissions_alternate_and_reveal_after_both_commit():
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(19, ["alice", "bob"])
    state = {"players": [{"player_id": "alice"}, {"player_id": "bob"}], "game_data": game_data}

    first = validator.get_legal_moves(state, "bob")[0]
    state["game_data"] = validator.apply_move(state, first)["game_data"]
    assert state["game_data"]["current_player"] == "alice"
    assert validator.get_legal_moves(state, "bob") == []

    second = validator.get_legal_moves(state, "alice")[0]
    state["game_data"] = validator.apply_move(state, second)["game_data"]
    assert state["game_data"]["current_phase"] == "headline_reveal_ready"
    assert state["game_data"]["current_player"] == "bob"
    assert validator.get_legal_moves(state, "bob")[0]["type"] == "reveal_headlines"


def test_unhandled_headline_is_not_offered_at_commit(monkeypatch):
    from app.games.twilight_struggle import state as state_module

    original_standard_deck = state_module.standard_deck

    def unhandled_deck(*args, **kwargs):
        # Strip every handler so no headline can resolve.
        return [{**card, "effect_handler": None} for card in original_standard_deck(*args, **kwargs)]

    monkeypatch.setattr(state_module, "standard_deck", unhandled_deck)
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(0, ["alice", "bob"])
    state = {"players": [{"player_id": "alice"}, {"player_id": "bob"}], "game_data": game_data}
    # Fail closed at commit: an unsupported headline is never offered, so reveal cannot fail mid-resolution.
    assert validator.get_legal_moves(state, "bob") == []
    assert validator.get_legal_moves(state, "alice") == []


def test_screen_serialization_never_exposes_other_faction_or_deck_order():
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(23)
    visible = validator.serialize_for_screen(game_data)

    assert "hands" not in visible
    assert "draw_pile" not in visible
    assert "rng_state_json" not in visible
    assert visible["hand"] == game_data["hands"]["ussr"]
    assert visible["hand_count"] == {
        "us": len(game_data["hands"]["us"]),
        "ussr": len(game_data["hands"]["ussr"]),
    }


def test_action_round_limits_and_scoring_card_turn_end_are_enforced():
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(51)
    game_data["current_phase"] = "action_round"
    game_data["actions_taken"] = {"us": 6, "ussr": 0}
    state = {"game_data": game_data}
    assert validator.get_legal_moves(state, "player_1") == []

    game_data["current_phase"] = "turn_end"
    game_data["actions_taken"] = {"us": 6, "ussr": 6}
    game_data["current_player"] = "player_2"
    game_data["hands"]["ussr"].append({"id": 999, "scoring": True})
    assert validator.get_legal_moves(state, "player_2") == []


def test_selected_defcon_is_required_only_for_how_i_learned_event():
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(53)
    game_data["current_phase"] = "action_round"
    game_data["current_player"] = "player_2"
    game_data["current_player_faction"] = "ussr"
    event_card = {"id": 46, "name": "How I Learned to Stop Worrying*", "operations": 2, "alignment": "both", "scoring": False, "effect_handler": "how_i_learned_to_stop_worrying"}
    game_data["hands"]["ussr"] = [event_card]
    state = {"game_data": game_data}
    basic = {"move_id": "test-card", "type": "play_card", "player_id": "player_2", "card_id": 46, "mode": "event"}

    assert not validator.validate_move(state, basic)
    assert validator.validate_move(state, {**basic, "chosen_defcon": 3})
