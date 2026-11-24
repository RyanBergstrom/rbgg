from fastapi.testclient import TestClient

from app import app
from app.games.fields_of_fire.validator import FieldsOfFireValidator
from app.games.fields_of_fire.terrain import terrain_card, get_card, get_deck, list_decks
from app.games.fields_of_fire.serialize import serialize_game_data


def test_initial_state():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    assert gd["phase"] == "setup"
    assert gd["current_player"] == "player_1"


def test_start_mission_transition():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    # Place all units
    for u in gd["company"]["units"]:
        u["position"] = 0
    for veh in gd["company"]["vehicles"]:
        veh["position"] = 0
    state = {"game_data": gd, "players": []}
    moves = v.get_legal_moves(state, "player_1")
    assert any(m["type"] == "start_mission" for m in moves)
    start_move = [m for m in moves if m["type"] == "start_mission"][0]
    new = v.apply_move(state, start_move)
    # 3.1: Friendly Higher HQ Event starts on Turn 2, so Turn 1 goes straight to Friendly Command.
    assert new["game_data"]["phase"] == "friendly_command"


def test_start_mission_on_turn_two_runs_higher_hq_event():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    gd["turn"] = 2
    for u in gd["company"]["units"]:
        u["position"] = 0
    for veh in gd["company"]["vehicles"]:
        veh["position"] = 0
    state = {"game_data": gd, "players": []}
    start_move = [m for m in v.get_legal_moves(state, "player_1") if m["type"] == "start_mission"][0]
    new = v.apply_move(state, start_move)
    assert new["game_data"]["phase"] == "friendly_higher_hq_event"


def test_optional_vehicles_do_not_block_setup_completion():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    for unit in gd["company"]["units"]:
        unit["position"] = 0

    complete, reason = v.is_setup_complete(gd)

    assert complete is True
    assert reason == "setup complete"


def test_vehicle_marked_required_must_be_placed_before_start():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    for unit in gd["company"]["units"]:
        unit["position"] = 0
    gd["company"]["vehicles"][0]["setup_required"] = True

    complete, reason = v.is_setup_complete(gd)

    assert complete is False
    assert reason == "1 vehicles not placed"


def test_stacking_limits_count_steps_and_not_counter_count():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    gd["phase"] = "friendly_command"
    gd["company"]["units"] = [
        {"id": f"squad_{index}", "type": "squad", "steps": 3, "position": 1}
        for index in range(5)
    ]
    gd["company"]["units"].extend([
        {"id": "one_step", "type": "hq", "steps": 1, "position": None},
        {"id": "three_step", "type": "squad", "steps": 3, "position": None},
    ])
    state = {"game_data": gd}

    # Five units occupy 15 steps, so another one-step unit still fits.
    assert v.validate_move(state, {
        "type": "place_unit", "unit_id": "one_step", "position": 1,
    }) is True
    gd["company"]["units"][-2]["position"] = 1
    # The next three-step squad would exceed the 16-step card cap.
    assert v.validate_move(state, {
        "type": "place_unit", "unit_id": "three_step", "position": 1,
    }) is False


def test_stacking_limits_exempt_staging_and_exclude_casualties_and_embarked():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data("normandy_mission_1")
    gd["company"]["units"] = [
        {"id": f"squad_{index}", "type": "squad", "steps": 3, "position": 4}
        for index in range(6)
    ]
    gd["company"]["units"].append({"id": "new_squad", "type": "squad", "steps": 3, "position": None})
    gd["company"]["casualties"] = [{"id": "squad_0"}]
    gd["company"]["units"][1]["embarked_in"] = "jeep_1"
    gd["phase"] = "friendly_command"  # Terrain placement is validated here; setup placement is staging-only.
    state = {"game_data": gd}

    # 12 active unembarked steps plus a 3-step squad fit under the 16-step cap.
    assert v.validate_move(state, {
        "type": "place_unit", "unit_id": "new_squad", "position": 4,
    }) is True
    # Staging-area cards are explicitly exempt from stacking limits.
    gd["company"]["units"] = [
        {"id": f"squad_{index}", "type": "squad", "steps": 3, "position": 0}
        for index in range(8)
    ]
    gd["company"]["units"].append({"id": "extra_squad", "type": "squad", "steps": 3, "position": None})
    assert v.validate_move(state, {
        "type": "place_unit", "unit_id": "extra_squad", "position": 0,
    }) is True


def test_move_whole_stack_respects_step_cap_and_moves_together():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    gd["phase"] = "friendly_command"
    gd["company"]["units"] = [
        {"id": "squad_a", "type": "squad", "steps": 3, "position": 0},
        {"id": "squad_b", "type": "squad", "steps": 3, "position": 0},
        *[
            {"id": f"other_{index}", "type": "squad", "steps": 3, "position": 1}
                for index in range(4)
        ],
    ]
    state = {"game_data": gd}
    move = {
        "type": "move_stack", "unit_ids": ["squad_a", "squad_b"],
        "from_position": 0, "to_position": 1,
    }
    assert v.validate_move(state, move) is False  # 12 + 6 exceeds 16
    move["unit_ids"] = ["squad_a"]
    assert v.validate_move(state, move) is True
    applied = v.apply_move(state, move)
    moved = {unit["id"]: unit["position"] for unit in applied["game_data"]["company"]["units"]}
    assert moved["squad_a"] == 1
    assert moved["squad_b"] == 0


def test_enemy_stacking_obeys_separate_step_limit():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    gd["phase"] = "enemy_activity"
    gd["enemy"] = [
        {"id": f"enemy_{index}", "type": "infantry", "steps": 3, "position": 1}
        for index in range(5)
    ]
    state = {"game_data": gd}

    assert v.validate_move(state, {
        "type": "place_enemy", "enemy_id": "enemy_fit", "enemy_type": "infantry",
        "strength": "squad", "steps": 1, "position": 1,
    }) is True
    assert v.validate_move(state, {
        "type": "place_enemy", "enemy_id": "enemy_over", "enemy_type": "infantry",
        "strength": "squad", "steps": 2, "position": 1,
    }) is False


def test_vehicle_stacking_limit_is_four_per_card():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["N01"] * 12
    gd["phase"] = "friendly_command"
    gd["company"]["vehicles"] = [
        {"id": f"vehicle_{index}", "type": "vehicle", "position": 1}
        for index in range(4)
    ] + [{"id": "vehicle_5", "type": "vehicle", "position": None}]
    state = {"game_data": gd}

    assert v.validate_move(state, {
        "type": "place_vehicle", "vehicle_id": "vehicle_5", "position": 1,
    }) is False
    assert v.validate_move(state, {
        "type": "place_vehicle", "vehicle_id": "vehicle_5", "position": 2,
    }) is True


def test_move_vehicle_respects_stacking_limit_and_source_position():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["map"]["cards"] = ["N01"] * 12
    gd["company"]["vehicles"] = [
        {"id": f"parked_{index}", "type": "vehicle", "position": 1}
        for index in range(4)
    ] + [{"id": "moving_vehicle", "type": "vehicle", "position": 0}]
    state = {"game_data": gd}

    assert v.validate_move(state, {
        "type": "move_vehicle", "vehicle_id": "moving_vehicle",
        "from_position": 0, "to_position": 1,
    }) is False
    assert v.validate_move(state, {
        "type": "move_vehicle", "vehicle_id": "moving_vehicle",
        "from_position": 0, "to_position": 2,
    }) is True
    assert v.validate_move(state, {
        "type": "move_vehicle", "vehicle_id": "moving_vehicle",
        "from_position": 3, "to_position": 2,
    }) is False


def test_destroyed_vehicles_never_count_and_wrecks_count_only_at_landing_zones():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["map"]["cards"] = ["N01"] * 12
    gd["company"]["vehicles"] = [
        {"id": f"wreck_{index}", "type": "vehicle", "status": "wrecked", "position": 1}
        for index in range(4)
    ] + [
        {"id": "destroyed", "type": "vehicle", "status": "destroyed", "position": 1},
        {"id": "incoming", "type": "vehicle", "position": 0},
    ]
    state = {"game_data": gd}
    move = {
        "type": "move_vehicle", "vehicle_id": "incoming",
        "from_position": 0, "to_position": 1,
    }

    assert v.validate_move(state, move) is True
    gd["landing_zones"] = [1]
    assert v.validate_move(state, move) is False
    gd["company"]["vehicles"] = gd["company"]["vehicles"][:3] + gd["company"]["vehicles"][4:]
    assert v.validate_move(state, move) is True


def test_legal_moves_include_whole_stack_destinations():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["map"] = {"rows": 3, "cols": 4, "cards": ["N01"] * 12}
    gd["company"]["units"] = [
        {"id": "squad_a", "type": "squad", "steps": 3, "position": 0},
        {"id": "squad_b", "type": "squad", "steps": 3, "position": 0},
    ]

    moves = v.get_legal_moves({"game_data": gd}, "player_1")
    assert any(
        move.get("type") == "move_stack"
        and move.get("unit_ids") == ["squad_a", "squad_b"]
        and move.get("from_position") == 0
        and move.get("to_position") == 1
        for move in moves
    )


def test_last_placed_counter_gets_highest_stack_order():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["map"]["cards"] = ["DZ_NORMANDY"] + ["N01"] * 11
    gd["company"]["units"] = [
        {"id": "first", "type": "hq", "position": None},
        {"id": "second", "type": "squad", "position": None},
    ]
    state = {"game_data": gd}
    state = v.apply_move(state, {"type": "place_unit", "unit_id": "first", "position": 0})
    state = v.apply_move(state, {"type": "place_unit", "unit_id": "second", "position": 0})

    order = {unit["id"]: unit["stack_order"] for unit in state["game_data"]["company"]["units"]}
    assert order["second"] > order["first"]


def test_new_card_placements_create_separate_stacks_and_stack_adds_join_selected_id():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["map"] = {"rows": 3, "cols": 4, "cards": ["N01"] * 12}
    gd["company"]["units"] = [
        {"id": unit_id, "type": "squad", "steps": 3, "position": None}
        for unit_id in ("first", "second", "third")
    ]
    state = {"game_data": gd}

    state = v.apply_move(state, {
        "type": "place_unit", "unit_id": "first", "position": 1, "stack_id": "pile-a",
    })
    state = v.apply_move(state, {
        "type": "place_unit", "unit_id": "second", "position": 1, "stack_id": "pile-b",
    })
    state = v.apply_move(state, {
        "type": "place_unit", "unit_id": "third", "position": 1, "stack_id": "pile-a",
    })

    units = state["game_data"]["company"]["units"]
    assert {unit["id"]: unit["stack_id"] for unit in units} == {
        "first": "pile-a", "second": "pile-b", "third": "pile-a",
    }
    moves = v.get_legal_moves(state, "player_1")
    pile_a_move = next(move for move in moves if move.get("type") == "move_stack" and move.get("stack_id") == "pile-a")
    assert set(pile_a_move["unit_ids"]) == {"first", "third"}


def test_setup_placement_is_staging_only():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data("training_1")
    position = next(i for i in range(len(gd["map"]["cards"])) if i not in gd["deployment_zones"])
    staging = gd["deployment_zones"][0]
    unit = next(unit for unit in gd["company"]["units"] if unit.get("position") is None)
    state = {"game_data": gd}

    assert v.validate_move(state, {
        "type": "place_unit", "unit_id": unit["id"], "position": position,
        "stack_id": "new-card-stack",
    }) is False
    assert v.validate_move(state, {
        "type": "place_unit", "unit_id": unit["id"], "position": staging,
        "stack_id": "new-card-stack",
    }) is True


def test_normandy_mission_one_can_start_with_campaign_roster():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data("normandy_mission_1")
    for unit in gd["company"]["units"]:
        if unit.get("setup_required", True):
            unit["position"] = 0
    state = {"game_data": gd, "players": []}

    start_move = next(
        move for move in v.get_legal_moves(state, "player_1")
        if move["type"] == "start_mission"
    )
    assert v.validate_move(state, start_move)
    # Turn 1 skips the Friendly Higher HQ Event (rule 3.1 starts on Turn 2).
    assert v.apply_move(state, start_move)["game_data"]["phase"] == "friendly_command"


def test_terrain_card_from_csv_starter1():
    card = terrain_card("hill", "N01")
    assert card["card_id"] == "N01"
    assert card["type"] == "hill"
    assert card["name"] == "Hill"
    assert card["cover_high"] == 0
    assert card["cover_low"] == 0
    assert card["elevation"] == 1
    assert card["trafficability"] == "fair"


def test_terrain_card_from_csv_woods():
    card = terrain_card("woods", "N17")
    assert card["card_id"] == "N17"
    assert card["type"] == "woods"
    assert card["name"] == "Woods"
    assert card["cover_high"] == 2
    assert card["cover_low"] == 2
    assert card["borders"] == ["dark", "dark", "dark", "dark"]


def test_normandy_validated_json_overrides_csv_for_game_terrain():
    woods = terrain_card("hill", "N17")
    assert woods["type"] == "woods"
    assert (woods["cover_high"], woods["cover_low"]) == (2, 2)
    assert woods["cover_potential"] == 3
    assert woods["cover_draw"] == 4

    hedgerow = terrain_card("open_field", "N27")
    assert hedgerow["type"] == "hedgerow_bocage"
    assert (hedgerow["cover_high"], hedgerow["cover_low"]) == (2, 1)

    cemetery = terrain_card("open_field", "N55")
    assert cemetery["type"] == "cemetery"
    assert cemetery["name"] == "Cemetery"


def test_get_deck_starter1():
    deck = get_deck("Starter 1 Terrain")
    assert len(deck) == 54
    assert all("card_id" in c for c in deck)
    assert all(c["deck"] == "Starter 1 Terrain" for c in deck)


def test_get_normandy_deck_uses_validated_catalog():
    deck = get_deck("Normandy Terrain")
    assert len(deck) == 55
    assert [card["card_id"] for card in deck] == [f"N{i:02d}" for i in range(1, 56)]
    assert all(card["deck"] == "Normandy Terrain" for card in deck)
    assert deck[16]["terrain_type"] == "woods"
    assert deck[16]["cover_draw"] == 4


def test_normandy_mission_one_initializes_playable_map_and_staging_zone():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data("normandy_mission_1")

    assert gd["map"]["rows"] == 4  # one staging row plus three mission rows
    assert gd["map"]["cols"] == 4
    assert gd["map"]["decks"] == ["Normandy Terrain"]
    assert gd["deployment_zones"] == [0, 1, 2, 3]
    assert gd["map"]["cards"][:4] == ["DZ_NORMANDY"] * 4
    terrain_cards = gd["map"]["cards"][4:]
    assert len(terrain_cards) == 12
    assert all(card_id in {f"N{i:02d}" for i in range(1, 56)} for card_id in terrain_cards)
    assert len(set(terrain_cards)) == len(terrain_cards)

    units = gd["company"]["units"]
    required_units = [unit for unit in units if unit.get("setup_required", True)]
    assert len(required_units) == 25
    assert len({unit["id"] for unit in units}) == len(units)
    assert sum(unit["type"] == "squad" for unit in units) == 9
    assert sum(unit["type"] == "mortar_team" for unit in units) == 3
    assert sum(unit["type"] == "at_team" for unit in units) == 3
    assert any(unit["id"] == "arty_fo" and unit["type"] == "forward_observer" for unit in units)
    assert gd["company"]["command"]["co_hq"] == "co_hq_1"
    assert gd["company"]["command"]["co_staff"] == ["co_xo", "co_1sg"]
    assert gd["company"]["vehicles"] == [{
        "id": "jeep_1", "type": "vehicle", "vehicle": "jeep",
        "position": None, "setup_required": False,
    }]


def test_game_serialization_includes_card_specific_terrain_image():
    serialized = serialize_game_data({
        "map": {"rows": 1, "cols": 2, "cards": ["N01", "DZ_NORMANDY"]},
        "deployment_zones": [1],
        "scenario_id": "normandy_mission_1",
    })
    card = serialized["map"]["cards"][0]
    zone = serialized["map"]["cards"][1]

    assert card["card_id"] == "N01"
    assert card["id"] == "N01"
    assert card["image"].startswith("/api/v1/img/fof/")
    assert zone["deployment_zone"] is True
    assert serialized["deployment_zones"] == [1]
    assert serialized["scenario_id"] == "normandy_mission_1"


def test_fof_static_mount_serves_terrain_and_normandy_card_back_images():
    client = TestClient(app)

    terrain_response = client.get(
        "/api/v1/img/fof/cards/N21%20Woods.jpg"
    )
    back_response = client.get(
        "/api/v1/img/fof/cards/Card%20Back%20-%20Normandy.jpg"
    )

    assert terrain_response.status_code == 200
    assert terrain_response.headers["content-type"].startswith("image/")
    assert back_response.status_code == 200
    assert back_response.headers["content-type"].startswith("image/")


def test_fields_of_fire_screen_state_serializes_normandy_map():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data("normandy_mission_1")
    screen_data = v.serialize_for_screen(gd)

    assert screen_data["map"]["cards"][4]["id"].startswith("N")
    assert screen_data["map"]["cards"][4]["image"].startswith("/api/v1/img/fof/")
    assert screen_data["deployment_zones"] == [0, 1, 2, 3]


def test_list_decks():
    decks = list_decks()
    assert "Starter 1 Terrain" in decks
    assert len(decks) > 0


def test_terrain_card_fallback_to_type():
    card = terrain_card("open_field", "A02")
    assert card["card_id"] == "A02"
    assert "type" in card


def test_lay_out_map():
    v = FieldsOfFireValidator()
    state = {"game_data": v.initial_game_data(), "players": []}
    moves = v.get_legal_moves(state, "player_1")
    lay_move = [m for m in moves if m["type"] == "lay_out_map"][0]
    lay_move["cards"] = ["N01"] * 12
    new = v.apply_move(state, lay_move)
    assert len(new["game_data"]["map"]["cards"]) == 12


def test_command_activation():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "friendly_command"
    gd["company"]["command"]["co_hq"] = "co_hq_1"
    gd["company"]["command"]["commands_pool"] = 1
    state = {"game_data": gd, "players": []}
    moves = v.get_legal_moves(state, "player_1")
    activate_moves = [m for m in moves if m["type"] == "activate_hq"]
    assert len(activate_moves) > 0
    # With the battalion HQ off map, the CO HQ is the first HQ to activate (3.3.1).
    co_move = next(m for m in activate_moves if m["hq_id"] == "co_hq_1")
    new = v.apply_move(state, co_move)
    # Activation marks the HQ as activated
    assert co_move["hq_id"] in new["game_data"]["company"]["command"]["activated"]


def test_place_unit():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["phase"] = "setup"
    gd["map"]["cards"] = ["DZ_NORMANDY"] + ["N01"] * 11
    state = {"game_data": gd, "players": []}
    move = {"type": "place_unit", "unit_id": "squad_1", "position": 0, "player_id": "player_1"}
    assert v.validate_move(state, move)
    new = v.apply_move(state, move)
    placed = [u for u in new["game_data"]["company"]["units"] if u.get("id") == "squad_1"]
    assert len(placed) == 1
    assert placed[0].get("position") == 0


def test_can_communicate():
    v = FieldsOfFireValidator()
    u1 = {"position": 0}
    u2 = {"position": 1}
    assert v.can_communicate(u1, u2) is True


def test_has_los():
    v = FieldsOfFireValidator()
    # Normandy Hill cards are confirmed to have dark borders; equal-height dense
    # terrain blocks LOS. Open Fields retain clear borders and allow LOS.
    ok, reason = v.has_los("N01", "N02")
    assert ok is False
    assert reason == "blocked by dense terrain"

    ok, reason = v.has_los("N42", "N43")
    assert ok is True


def test_get_elevation():
    v = FieldsOfFireValidator()
    elev = v.get_elevation("N01")
    assert isinstance(elev, int)


