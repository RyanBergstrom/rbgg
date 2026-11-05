from app.games.twilight_struggle.validator import TwilightStruggleValidator

PLAYERS = ["alice", "bob"]


def _state(gd):
    return {"players": [{"player_id": p} for p in PLAYERS], "game_data": gd}


def _action_round(validator, seed=11):
    gd = validator.initial_game_data(seed, PLAYERS)
    gd["current_phase"] = "action_round"
    gd["current_player_faction"] = "us"
    gd["current_player"] = "alice"
    gd["actions_taken"] = {"us": 0, "ussr": 0}
    gd["turn"] = 2
    return gd


def _card(card_id):
    from app.games.twilight_struggle.cards import load_standard_card_catalog

    return next(c for c in load_standard_card_catalog() if c["id"] == card_id)


def test_choice_required_event_is_rejected_without_choices_and_accepted_with_them():
    validator = TwilightStruggleValidator()
    gd = _action_round(validator)
    gd["hands"]["us"] = [_card(29)]  # East European Unrests: needs exactly three eligible choices
    state = _state(gd)
    base = {"type": "play_card", "player_id": "alice", "card_id": 29, "mode": "event"}

    assert not validator.validate_move(state, base)
    assert not validator.validate_move(state, {**base, "event_choices": {"east_european_unrests": ["Poland"]}})


def test_non_dict_event_choices_are_rejected():
    validator = TwilightStruggleValidator()
    gd = _action_round(validator)
    gd["hands"]["us"] = [_card(77)]
    base = {"type": "play_card", "player_id": "alice", "card_id": 77, "mode": "event"}
    assert not validator.validate_move(_state(gd), {**base, "event_choices": ["bad"]})


def test_choice_required_headline_is_not_offered():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(11, PLAYERS)
    # Clear USSR influence in Eastern Europe so East European Unrests has no legal default.
    for name in ("E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria"):
        gd["countries"][name]["ussr"] = 0
    gd["hands"]["us"] = [_card(29)]  # needs choices; with no legal default it cannot be committed
    moves = validator.get_legal_moves(_state(gd), "alice")
    assert all(move.get("card_id") != 29 for move in moves)


def test_kal_007_bonus_is_offered_only_while_active_for_us():
    validator = TwilightStruggleValidator()
    gd = _action_round(validator)
    gd["persistent_events"] = {"kal_007_bonus": {"faction": "us", "operations": 4, "expires_turn": 2}}
    bonus_templates = [m for m in validator.get_legal_moves(_state(gd), "alice") if m["type"] == "kal_007_bonus"]
    assert len(bonus_templates) == 1

    gd["persistent_events"] = {}
    assert not [m for m in validator.get_legal_moves(_state(gd), "alice") if m["type"] == "kal_007_bonus"]


def test_kal_007_bonus_validates_and_applies_without_spending_action_round():
    validator = TwilightStruggleValidator()
    gd = _action_round(validator)
    gd["persistent_events"] = {"kal_007_bonus": {"faction": "us", "operations": 4, "expires_turn": 2}}
    state = _state(gd)
    move = {"type": "kal_007_bonus", "player_id": "alice", "operations_action": {"type": "influence", "placements": []}}

    assert validator.validate_move(state, move)
    result = validator.apply_move(state, move)["game_data"]
    assert "kal_007_bonus" not in result["persistent_events"]
    assert result["actions_taken"] == {"us": 0, "ussr": 0}
    assert result["current_phase"] == "action_round"


def test_kal_007_bonus_rejects_coup_and_template_without_payload():
    validator = TwilightStruggleValidator()
    gd = _action_round(validator)
    gd["persistent_events"] = {"kal_007_bonus": {"faction": "us", "operations": 4, "expires_turn": 2}}
    state = _state(gd)
    assert not validator.validate_move(state, {"type": "kal_007_bonus", "player_id": "alice"})
    assert not validator.validate_move(
        state, {"type": "kal_007_bonus", "player_id": "alice", "operations_action": {"type": "coup", "country": "Mexico"}},
    )
