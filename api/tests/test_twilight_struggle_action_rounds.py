from app.core.rng import create_rng, serialize_rng
from app.games.twilight_struggle.action_rounds import _server_resolve_random_inputs
from app.games.twilight_struggle.validator import TwilightStruggleValidator


def test_client_supplied_coup_roll_is_replaced_by_server_rng():
    first_rng = create_rng(123)
    second_rng = create_rng(123)
    first = _server_resolve_random_inputs(
        {"type": "coup", "country": "Italy", "die_roll": 6}, first_rng
    )
    second = _server_resolve_random_inputs(
        {"type": "coup", "country": "Italy", "die_roll": 1}, second_rng
    )

    assert first["die_roll"] == second["die_roll"]
    assert 1 <= first["die_roll"] <= 6
    assert serialize_rng(first_rng) == serialize_rng(second_rng)


def test_validator_rejects_illegal_and_accepts_legal_coup_payload():
    validator = TwilightStruggleValidator()
    game_data = validator.initial_game_data(31)
    game_data["current_phase"] = "action_round"
    game_data["current_player"] = "player_2"
    game_data["current_player_faction"] = "ussr"
    game_data["countries"]["Italy"]["us"] = 1
    card = next(card for card in game_data["hands"]["ussr"] if not card["scoring"])
    state = {"game_data": game_data}
    base_move = {
        "move_id": "test-play",
        "type": "play_card",
        "player_id": "player_2",
        "card_id": card["id"],
        "mode": "operations",
    }

    assert validator.validate_move(
        state,
        {**base_move, "operations_action": {"type": "coup", "country": "Italy", "die_roll": 1}},
    )
    assert not validator.validate_move(
        state,
        {**base_move, "operations_action": {"type": "coup", "country": "Atlantis"}},
    )
    assert not validator.validate_move(
        state,
        {**base_move, "operations_action": {"type": "unknown_kind"}},
    )
    assert not validator.validate_move(
        state,
        {
            **base_move,
            "operations_action": {"type": "coup", "country": "Italy"},
            "trigger_own_event": [],
        },
    )
