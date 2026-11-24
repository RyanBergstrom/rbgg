from app.games.fields_of_fire import validator as validator_module
from app.games.fields_of_fire.combat_resolution import RESULTS
from app.games.fields_of_fire.validator import FieldsOfFireValidator


def _table(result_for_zero):
    entries = [f"{m:+d} {result_for_zero}" if m else f"0 {result_for_zero}" for m in range(-4, 7)]
    return "; ".join(entries)


def _state(vof_markers=None, units=None):
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "mutual_combat"
    gd["map"]["cards"] = ["N01"] * 3
    gd["map"]["rows"] = 1
    gd["map"]["cols"] = 3
    gd["vof_markers"] = list(vof_markers or [])
    gd["company"]["units"] = list(units or [])
    return v, {"game_data": gd}


def test_fire_is_not_offered_without_a_vof_marker():
    v, state = _state()
    fires = [m for m in v.get_legal_moves(state, "p1") if m["type"] == "fire"]
    assert fires == []


def test_fire_is_offered_on_a_card_with_a_vof_marker():
    v, state = _state(vof_markers=[{"position": 1, "value": -1}])
    fires = [m for m in v.get_legal_moves(state, "p1") if m["type"] == "fire"]
    assert [m["position"] for m in fires] == [1]


def test_fire_on_a_card_without_vof_is_rejected():
    v, state = _state(vof_markers=[{"position": 1, "value": -1}])
    assert v.validate_move(state, {"type": "fire", "position": 2}) is False


def test_fire_records_a_result_from_the_drawn_card():
    v, state = _state(vof_markers=[{"position": 1, "value": -3}])
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["position"] == 1
    assert record["net_modifier"] == -3
    assert record["result"] in RESULTS
    assert record["card_id"].startswith("FOF-ACTION-")


def test_pin_result_pins_units_on_the_card(monkeypatch):
    fake = {"action_details": {"combat_resolution": _table("PIN")}}
    monkeypatch.setattr(validator_module, "get_action_card", lambda _cid: fake)
    units = [
        {"id": "u1", "position": 1, "status": "good_order"},
        {"id": "u2", "position": 0, "status": "good_order"},
    ]
    v, state = _state(vof_markers=[{"position": 1, "value": 0}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    by_id = {u["id"]: u for u in new_gd["company"]["units"]}
    assert by_id["u1"]["status"] == "pinned"
    assert by_id["u2"]["status"] == "good_order"
    assert new_gd["fire_results"][-1]["result"] == "PIN"

def test_screen_data_exposes_the_last_fire_result():
    v, state = _state(vof_markers=[{"position": 1, "value": -3}])
    assert v.serialize_for_screen(state["game_data"])["last_fire_result"] is None
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    shown = v.serialize_for_screen(new_gd)["last_fire_result"]
    assert shown["position"] == 1
    assert shown["result"] in RESULTS

def test_fire_net_modifier_adds_terrain_cover_value(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: {"cover_low": 2, "cover_high": 3})
    v, state = _state(vof_markers=[{"position": 1, "value": -1}])
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["vof_modifier"] == -1
    assert record["cover_modifier"] == 2
    assert record["net_modifier"] == 1


def test_fire_with_no_terrain_cover_uses_vof_only(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: {"cover_low": 0, "cover_high": 0})
    v, state = _state(vof_markers=[{"position": 1, "value": -3}])
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["cover_modifier"] == 0
    assert record["net_modifier"] == -3

def _cover_card(borders):
    return {"borders": borders, "cover_high": 3, "cover_low": 1}


def test_fire_entering_a_dark_border_uses_high_cover(monkeypatch):
    # Fire from card 0 enters card 1 through its west side. West is dark here.
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: _cover_card(["white", "white", "white", "dark"]))
    v, state = _state(vof_markers=[{"position": 1, "value": -1}])
    new_gd = v.apply_move(state, {"type": "fire", "position": 1, "from_position": 0})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["cover_modifier"] == 3
    assert record["cover_source"] == "high"
    assert record["net_modifier"] == 2


def test_fire_entering_only_white_borders_uses_low_cover(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: _cover_card(["white"] * 4))
    v, state = _state(vof_markers=[{"position": 1, "value": -1}])
    new_gd = v.apply_move(state, {"type": "fire", "position": 1, "from_position": 0})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["cover_modifier"] == 1
    assert record["cover_source"] == "low"


def test_fire_from_within_the_card_uses_low_cover_even_with_dark_borders(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: _cover_card(["dark"] * 4))
    v, state = _state(vof_markers=[{"position": 1, "value": -1}])
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["cover_modifier"] == 1
    assert record["cover_source"] == "low"


def test_fire_is_offered_from_each_friendly_origin_and_from_the_card_itself():
    v, state = _state(
        vof_markers=[{"position": 1, "value": -1}],
        units=[{"id": "u1", "position": 0, "status": "good_order"}],
    )
    fires = [m for m in v.get_legal_moves(state, "p1") if m["type"] == "fire"]
    assert {m["from_position"] for m in fires} == {0, 1}

def test_each_unit_on_the_target_card_gets_its_own_draw():
    units = [
        {"id": "u1", "position": 1, "status": "good_order"},
        {"id": "u2", "position": 1, "status": "good_order"},
    ]
    v, state = _state(vof_markers=[{"position": 1, "value": -1}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    records = new_gd["fire_results"]
    assert [r["unit_id"] for r in records] == ["u1", "u2"]
    assert all(r["card_id"].startswith("FOF-ACTION-") for r in records)


def test_pin_only_affects_the_unit_drawn_for(monkeypatch):
    results = iter([_table("PIN"), _table("MISS")])
    fakes = {"PIN": {"action_details": {"combat_resolution": _table("PIN")}},
             "MISS": {"action_details": {"combat_resolution": _table("MISS")}}}
    sequence = ["PIN", "MISS"]
    calls = {"n": 0}

    def fake_card(_cid):
        kind = sequence[calls["n"]]
        calls["n"] += 1
        return fakes[kind]

    monkeypatch.setattr(validator_module, "get_action_card", fake_card)
    units = [
        {"id": "u1", "position": 1, "status": "good_order"},
        {"id": "u2", "position": 1, "status": "good_order"},
    ]
    v, state = _state(vof_markers=[{"position": 1, "value": 0}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    by_id = {u["id"]: u for u in new_gd["company"]["units"]}
    assert by_id["u1"]["status"] == "pinned"
    assert by_id["u2"]["status"] == "good_order"

def test_pinned_defender_adds_plus_one(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: {"cover_low": 0, "cover_high": 0})
    units = [{"id": "u1", "position": 1, "status": "pinned"}]
    v, state = _state(vof_markers=[{"position": 1, "value": -1}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["status_modifier"] == 1
    assert record["net_modifier"] == 0


def test_exposed_defender_adds_minus_two(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: {"cover_low": 0, "cover_high": 0})
    units = [{"id": "u1", "position": 1, "status": "exposed"}]
    v, state = _state(vof_markers=[{"position": 1, "value": 0}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    record = new_gd["fire_results"][-1]
    assert record["status_modifier"] == -2
    assert record["net_modifier"] == -2


def test_good_order_defender_has_no_status_modifier(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: {"cover_low": 0, "cover_high": 0})
    units = [{"id": "u1", "position": 1, "status": "good_order"}]
    v, state = _state(vof_markers=[{"position": 1, "value": -1}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    assert new_gd["fire_results"][-1]["status_modifier"] == 0

def _move_state(units, phase="friendly_command"):
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = phase
    gd["map"]["cards"] = ["N01"] * 3
    gd["map"]["rows"] = 1
    gd["map"]["cols"] = 3
    gd["company"]["units"] = units
    return v, {"game_data": gd}


def test_moving_between_cards_in_play_marks_the_unit_exposed():
    v, state = _move_state([{"id": "u1", "position": 0, "status": "good_order"}])
    move = {"type": "move_unit", "unit_id": "u1", "from_position": 0, "to_position": 1}
    new_gd = v.apply_move(state, move)["game_data"]
    assert new_gd["company"]["units"][0]["exposed"] is True


def test_exposed_unit_cannot_move_to_another_card():
    v, state = _move_state([{"id": "u1", "position": 0, "status": "good_order", "exposed": True}])
    move = {"type": "move_unit", "unit_id": "u1", "from_position": 0, "to_position": 1}
    assert v.validate_move(state, move) is False


def test_clean_up_clears_the_exposed_marker():
    v, state = _move_state([{"id": "u1", "position": 1, "status": "good_order", "exposed": True}], phase="clean_up")
    new_gd = v.apply_move(state, {"type": "advance_phase", "next_phase": "friendly_higher_hq_event"})["game_data"]
    assert new_gd["company"]["units"][0]["exposed"] is False


def test_exposed_unit_fire_uses_minus_two(monkeypatch):
    monkeypatch.setattr(validator_module, "get_card", lambda _cid: {"cover_low": 0, "cover_high": 0})
    units = [{"id": "u1", "position": 1, "status": "good_order", "exposed": True}]
    v, state = _state(vof_markers=[{"position": 1, "value": 0}], units=units)
    new_gd = v.apply_move(state, {"type": "fire", "position": 1})["game_data"]
    assert new_gd["fire_results"][-1]["status_modifier"] == -2

def test_stack_with_an_exposed_unit_cannot_move_to_another_card():
    units = [
        {"id": "u1", "position": 0, "status": "good_order", "exposed": True},
        {"id": "u2", "position": 0, "status": "good_order", "exposed": False},
    ]
    v, state = _move_state(units)
    move = {"type": "move_stack", "unit_ids": ["u1", "u2"], "from_position": 0, "to_position": 1}
    assert v.validate_move(state, move) is False


def test_stack_of_unexposed_units_can_move_between_cards():
    units = [
        {"id": "u1", "position": 0, "status": "good_order", "exposed": False},
        {"id": "u2", "position": 0, "status": "good_order", "exposed": False},
    ]
    v, state = _move_state(units)
    move = {"type": "move_stack", "unit_ids": ["u1", "u2"], "from_position": 0, "to_position": 1}
    assert v.validate_move(state, move) is True

def _infil_state(units, vof_positions=(), commands=3):
    v, state = _move_state(units)
    gd = state["game_data"]
    gd["vof_markers"] = [{"position": p, "value": -1} for p in vof_positions]
    gd["company"]["command"] = {"commands_pool": commands}
    return v, state


def _infil_move(to_pos=1):
    return {"type": "infiltrate", "unit_id": "u1", "from_position": 0, "to_position": to_pos}


def test_infiltrate_needs_a_vof_marker_on_origin_or_destination():
    units = [{"id": "u1", "position": 0, "status": "good_order"}]
    v, state = _infil_state(units, vof_positions=())
    assert v.validate_move(state, _infil_move()) is False
    v, state = _infil_state(units, vof_positions=(1,))
    assert v.validate_move(state, _infil_move()) is True


def test_infiltrate_rejects_exposed_or_non_good_order_units():
    units = [{"id": "u1", "position": 0, "status": "good_order", "exposed": True}]
    v, state = _infil_state(units, vof_positions=(1,))
    assert v.validate_move(state, _infil_move()) is False
    units = [{"id": "u1", "position": 0, "status": "pinned"}]
    v, state = _infil_state(units, vof_positions=(1,))
    assert v.validate_move(state, _infil_move()) is False


def test_successful_infiltrate_moves_unexposed_and_costs_a_command(monkeypatch):
    monkeypatch.setattr(validator_module, "get_action_card", lambda _cid: {"action_details": {"attempt_icons": ["Infiltrate"]}})
    units = [{"id": "u1", "position": 0, "status": "good_order"}]
    v, state = _infil_state(units, vof_positions=(1,), commands=3)
    new_gd = v.apply_move(state, _infil_move())["game_data"]
    unit = new_gd["company"]["units"][0]
    assert unit["position"] == 1
    assert unit["exposed"] is False
    assert new_gd["company"]["command"]["commands_pool"] == 2
    assert new_gd["infiltration_results"][-1]["success"] is True


def test_failed_infiltrate_becomes_an_exposed_move(monkeypatch):
    monkeypatch.setattr(validator_module, "get_action_card", lambda _cid: {"action_details": {"attempt_icons": ["Cover"]}})
    units = [{"id": "u1", "position": 0, "status": "good_order"}]
    v, state = _infil_state(units, vof_positions=(1,), commands=3)
    new_gd = v.apply_move(state, _infil_move())["game_data"]
    unit = new_gd["company"]["units"][0]
    assert unit["position"] == 1
    assert unit["exposed"] is True
    assert new_gd["company"]["command"]["commands_pool"] == 2
    assert new_gd["infiltration_results"][-1]["success"] is False


def test_infiltrate_is_offered_only_to_adjacent_cards():
    units = [{"id": "u1", "position": 0, "status": "good_order"}]
    v, state = _infil_state(units, vof_positions=(1, 2))
    dests = sorted(m["to_position"] for m in v.get_legal_moves(state, "p1") if m["type"] == "infiltrate")
    assert dests == [1]

def test_green_infiltrator_draws_one_card(monkeypatch):
    monkeypatch.setattr(validator_module, "get_action_card", lambda _cid: {"action_details": {"attempt_icons": ["Cover"]}})
    units = [{"id": "u1", "position": 0, "status": "good_order", "experience": "green"}]
    v, state = _infil_state(units, vof_positions=(1,), commands=3)
    new_gd = v.apply_move(state, _infil_move())["game_data"]
    assert len(new_gd["infiltration_results"][-1]["card_ids"]) == 1


def test_veteran_infiltrator_draws_three_cards(monkeypatch):
    monkeypatch.setattr(validator_module, "get_action_card", lambda _cid: {"action_details": {"attempt_icons": ["Cover"]}})
    units = [{"id": "u1", "position": 0, "status": "good_order", "experience": "veteran"}]
    v, state = _infil_state(units, vof_positions=(1,), commands=3)
    new_gd = v.apply_move(state, _infil_move())["game_data"]
    assert len(new_gd["infiltration_results"][-1]["card_ids"]) == 3


def test_tripod_or_h_rated_unit_cannot_infiltrate():
    for extra in ({"tripod": True}, {"vof_rating": "H"}, {"weapon": "mortar"}):
        units = [{"id": "u1", "position": 0, "status": "good_order", **extra}]
        v, state = _infil_state(units, vof_positions=(1,))
        assert v.validate_move(state, _infil_move()) is False, extra

def test_counter_mount_type_tripod_blocks_infiltration():
    units = [{"id": "u1", "position": 0, "status": "good_order", "mount_type": "Tripod"}]
    v, state = _infil_state(units, vof_positions=(1,))
    assert v.validate_move(state, _infil_move()) is False


def test_counter_mount_type_none_allows_infiltration():
    units = [{"id": "u1", "position": 0, "status": "good_order", "mount_type": None}]
    v, state = _infil_state(units, vof_positions=(1,))
    assert v.validate_move(state, _infil_move()) is True
