from app.games.fields_of_fire.turn_sequence import TURN_SEQUENCE
from app.games.fields_of_fire.validator import PHASES, FieldsOfFireValidator


def test_turn_sequence_covers_every_phase_in_order():
    assert [step["phase"] for step in TURN_SEQUENCE] == PHASES


def test_clean_up_starts_next_turn_at_higher_hq_event():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["turn"] = 1
    state = {"game_data": gd}
    move = {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"}

    assert v.validate_move(state, move) is True
    new_gd = v.apply_move(state, move)["game_data"]
    assert new_gd["phase"] == "friendly_higher_hq_event"
    assert new_gd["turn"] == 2


def test_clean_up_cannot_skip_to_game_over_before_turn_limit():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["turn"] = 1
    gd["duration_turns"] = 10
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "advance_phase", "next_phase": "game_over"}) is False


def test_reaching_turn_limit_ends_mission():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["turn"] = 2
    gd["duration_turns"] = 2
    state = {"game_data": gd}
    move = {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"}

    new_gd = v.apply_move(state, move)["game_data"]
    assert new_gd["turn"] == 3
    assert new_gd["phase"] == "game_over"


def test_screen_state_includes_turn_sequence_and_turn_limit():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data("normandy_mission_1")

    serialized = v.serialize_for_screen(gd)
    assert [step["phase"] for step in serialized["turn_sequence"]] == PHASES
    assert serialized["duration_turns"] == 10

def test_draw_commands_uses_activated_commands_from_drawn_card():
    from app.games.fields_of_fire.action_deck import force_next, get_action_card

    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["contact_level"] = "contact"
    gd["company"]["command"]["activated"] = ["co_hq_1"]
    force_next(gd["action_deck"], ["FOF-ACTION-001"])
    state = {"game_data": gd}

    new_gd = v.apply_move(state, {"type": "draw_commands"})["game_data"]
    expected = get_action_card("FOF-ACTION-001")["action_details"]["commands"]
    assert new_gd["company"]["command"]["commands_pool"] == expected
    assert new_gd["company"]["command"]["command_draw"][-1] == {"card": "FOF-ACTION-001", "commands": expected}


def test_draw_commands_uses_initiative_when_nothing_activated():
    from app.games.fields_of_fire.action_deck import force_next, get_action_card

    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["contact_level"] = "contact"
    force_next(gd["action_deck"], ["FOF-ACTION-002"])
    state = {"game_data": gd}

    new_gd = v.apply_move(state, {"type": "draw_commands"})["game_data"]
    expected = get_action_card("FOF-ACTION-002")["action_details"]["initiative"]
    assert new_gd["company"]["command"]["commands_pool"] == expected

def test_only_command_hqs_can_be_activated_and_only_once_per_turn():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["commands_pool"] = 5
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "co_hq_1"}) is True
    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "not_an_hq"}) is False
    state = v.apply_move(state, {"type": "activate_hq", "hq_id": "co_hq_1"})
    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "co_hq_1"}) is False


def test_spending_commands_cannot_exceed_pool():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["commands_pool"] = 2
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "spend_command", "amount": 2}) is True
    assert v.validate_move(state, {"type": "spend_command", "amount": 3}) is False


def test_turn_rollover_resets_activations():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["company"]["command"]["activated"] = ["co_hq_1"]
    state = {"game_data": gd}

    new_gd = v.apply_move(state, {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"})["game_data"]
    assert new_gd["company"]["command"]["activated"] == []

def test_platoon_hqs_need_co_hq_activated_first():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["commands_pool"] = 5
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "plt_hq_1"}) is False
    state = v.apply_move(state, {"type": "activate_hq", "hq_id": "co_hq_1"})
    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "plt_hq_1"}) is True


def test_co_hq_activates_first_when_battalion_hq_is_off_map():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["commands_pool"] = 5
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "co_hq_1"}) is True
    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "bn_hq_1"}) is False


def test_battalion_hq_must_activate_before_co_hq_when_on_map():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["commands_pool"] = 5
    for unit in gd["company"]["units"]:
        if unit["id"] == "bn_hq_1":
            unit["position"] = 0
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "co_hq_1"}) is False
    assert v.validate_move(state, {"type": "activate_hq", "hq_id": "bn_hq_1"}) is True

def test_legal_moves_offer_only_rule_valid_activations():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["commands_pool"] = 5
    state = {"game_data": gd, "players": []}

    offered = [m["hq_id"] for m in v.get_legal_moves(state, "player_1") if m["type"] == "activate_hq"]
    assert offered == ["co_hq_1"]

def test_hq_spend_limit_is_six_per_impulse_on_day():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["activated"] = ["co_hq_1", "plt_hq_1"]
    gd["company"]["command"]["pool_by_hq"] = {"co_hq_1": 20, "plt_hq_1": 20}
    gd["company"]["command"]["commands_pool"] = 40
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "spend_command", "amount": 6, "hq_id": "co_hq_1"}) is True
    state = v.apply_move(state, {"type": "spend_command", "amount": 6, "hq_id": "co_hq_1"})
    assert v.validate_move(state, {"type": "spend_command", "amount": 1, "hq_id": "co_hq_1"}) is False
    # A different HQ has its own cap.
    assert v.validate_move(state, {"type": "spend_command", "amount": 1, "hq_id": "plt_hq_1"}) is True


def test_hq_spend_limit_is_four_under_limited_visibility():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["visibility"] = {"limited": True}
    gd["company"]["command"]["activated"] = ["co_hq_1"]
    gd["company"]["command"]["pool_by_hq"] = {"co_hq_1": 20}
    gd["company"]["command"]["commands_pool"] = 20
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "spend_command", "amount": 4, "hq_id": "co_hq_1"}) is True
    assert v.validate_move(state, {"type": "spend_command", "amount": 5, "hq_id": "co_hq_1"}) is False


def test_turn_rollover_resets_hq_spend_counts():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["company"]["command"]["spent_by_hq"] = {"co_hq_1": 6}
    state = {"game_data": gd}

    new_gd = v.apply_move(state, {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"})["game_data"]
    assert new_gd["company"]["command"]["spent_by_hq"] == {}

def test_draw_credits_only_the_activated_hq_once_per_activation():
    from app.games.fields_of_fire.action_deck import force_next, get_action_card

    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["contact_level"] = "contact"
    gd["company"]["command"]["activated"] = ["co_hq_1"]
    force_next(gd["action_deck"], ["FOF-ACTION-001", "FOF-ACTION-002"])
    state = {"game_data": gd}

    assert v.validate_move(state, {"type": "draw_commands", "hq_id": "plt_hq_1"}) is False
    state = v.apply_move(state, {"type": "draw_commands", "hq_id": "co_hq_1"})
    expected = get_action_card("FOF-ACTION-001")["action_details"]["commands"]
    assert state["game_data"]["company"]["command"]["pool_by_hq"] == {"co_hq_1": expected}
    assert v.validate_move(state, {"type": "draw_commands", "hq_id": "co_hq_1"}) is False


def test_saved_commands_are_capped_by_experience_at_turn_end():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["turn"] = 1
    units = {u["id"]: u for u in gd["company"]["units"]}
    units["co_hq_1"]["experience"] = "green"
    units["plt_hq_1"]["experience"] = "veteran"
    gd["company"]["command"]["pool_by_hq"] = {"co_hq_1": 9, "plt_hq_1": 9}
    gd["company"]["command"]["commands_pool"] = 18
    state = {"game_data": gd}

    new_gd = v.apply_move(state, {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"})["game_data"]
    assert new_gd["company"]["command"]["pool_by_hq"] == {"co_hq_1": 3, "plt_hq_1": 9}
    assert new_gd["company"]["command"]["commands_pool"] == 12


def test_saved_cap_is_lower_under_limited_visibility():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "clean_up"
    gd["turn"] = 1
    gd["visibility"] = {"limited": True}
    gd["company"]["command"]["pool_by_hq"] = {"co_hq_1": 9}
    gd["company"]["command"]["commands_pool"] = 9
    state = {"game_data": gd}

    new_gd = v.apply_move(state, {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"})["game_data"]
    # co_hq_1 defaults to Line experience: 4 saved under limited visibility.
    assert new_gd["company"]["command"]["pool_by_hq"] == {"co_hq_1": 4}


def test_legal_moves_offer_draw_and_spend_for_each_activated_hq():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["activated"] = ["co_hq_1"]
    gd["company"]["command"]["pool_by_hq"] = {"co_hq_1": 6}
    gd["company"]["command"]["commands_pool"] = 6
    state = {"game_data": gd, "players": []}

    moves = v.get_legal_moves(state, "player_1")
    assert [m["hq_id"] for m in moves if m["type"] == "draw_commands"] == ["co_hq_1"]
    assert [m["hq_id"] for m in moves if m["type"] == "spend_command"] == ["co_hq_1"]

def test_draw_modifiers_green_minus_one_veteran_plus_one_and_no_contact_plus_one():
    from app.games.fields_of_fire.action_deck import force_next, get_action_card

    base = get_action_card("FOF-ACTION-001")["action_details"]["commands"]
    v = FieldsOfFireValidator()

    def draw_for(experience, contact="contact"):
        gd = v.initial_game_data()
        gd["phase"] = "friendly_command"
        gd["contact_level"] = contact
        gd["company"]["command"]["activated"] = ["co_hq_1"]
        for unit in gd["company"]["units"]:
            if unit["id"] == "co_hq_1":
                unit["experience"] = experience
        force_next(gd["action_deck"], ["FOF-ACTION-001"])
        state = {"game_data": gd}
        return v.apply_move(state, {"type": "draw_commands", "hq_id": "co_hq_1"})["game_data"]["company"]["command"]["pool_by_hq"]["co_hq_1"]

    assert draw_for("green") == max(1, base - 1)
    assert draw_for("veteran") == base + 1
    assert draw_for("line", contact="no_contact") == base + 1


def test_initiative_draw_can_be_zero_but_activated_draw_is_at_least_one():
    from app.games.fields_of_fire.action_deck import force_next, get_action_card

    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["contact_level"] = "contact"
    gd["company"]["command"]["activated"] = []
    force_next(gd["action_deck"], ["FOF-ACTION-001"])
    state = {"game_data": gd}
    initiative = get_action_card("FOF-ACTION-001")["action_details"]["initiative"]
    new_gd = v.apply_move(state, {"type": "draw_commands"})["game_data"]
    assert new_gd["company"]["command"]["commands_pool"] == max(0, initiative)

def test_screen_state_exposes_last_command_draw():
    from app.games.fields_of_fire.action_deck import force_next

    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["contact_level"] = "contact"
    gd["company"]["command"]["activated"] = ["co_hq_1"]
    force_next(gd["action_deck"], ["FOF-ACTION-001"])
    new_gd = v.apply_move({"game_data": gd}, {"type": "draw_commands", "hq_id": "co_hq_1"})["game_data"]

    shown = v.serialize_for_screen(new_gd)["last_command_draw"]
    assert shown["card"] == "FOF-ACTION-001"
    assert shown["card_number"] == 1
    assert shown["commands"] == new_gd["company"]["command"]["command_draw"][-1]["commands"]


def test_screen_state_last_command_draw_is_none_before_any_draw():
    v = FieldsOfFireValidator()
    assert v.serialize_for_screen(v.initial_game_data())["last_command_draw"] is None
