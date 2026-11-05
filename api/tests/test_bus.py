"""Regression coverage for the implemented Bus setup and drafting foundation."""

import pytest

from app.games.bus.validator import (
    BUILDING_SITES,
    EDGES,
    MAX_LINE_MARKERS_PER_PLAYER,
    NODES,
    CENTRAL_PARK_CROSSINGS,
    STATION_CROSSINGS,
    BusValidator,
)


def _state(data, players=3):
    return {
        "players": [{"player_id": f"player_{number}"} for number in range(1, players + 1)],
        "current_player_index": 0,
        "game_data": data,
    }


def _apply_first_move(validator, state, move_type=None):
    moves = validator.get_legal_moves(state, state["game_data"]["current_player"])
    move = next(move for move in moves if move_type is None or move["type"] == move_type)
    return {**state, **validator.apply_move(state, move)}


def test_bus_initial_state_uses_three_player_setup_and_time_stones():
    data = BusValidator().initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    assert data["current_phase"] == "SETUP_BUILDINGS"
    assert data["current_player"] == data["starting_player"]
    assert data["starting_player"] in data["players"]
    assert data["time_stones_remaining"] == 4
    assert data["building_tiles_remaining"] == {"house": 30, "office": 30, "pub": 30}
    assert set(data["passengers"].values()) == set(CENTRAL_PARK_CROSSINGS)
    assert all(player["action_markers"] == 20 for player in data["players"].values())


def test_bus_starting_player_is_deterministic_for_a_setup_seed():
    validator = BusValidator()
    player_ids = ["player_1", "player_2", "player_3"]
    first = validator.initial_game_data(rng_seed=13579, player_ids=player_ids)
    second = validator.initial_game_data(rng_seed=13579, player_ids=player_ids)
    assert first["starting_player"] == second["starting_player"]


def test_bus_four_and_five_player_setup_use_five_time_stones():
    validator = BusValidator()
    for count in (4, 5):
        player_ids = [f"player_{number}" for number in range(1, count + 1)]
        data = validator.initial_game_data(player_ids=player_ids)
        assert data["time_stones_remaining"] == 5
        assert list(data["players"]) == player_ids


def test_bus_topology_has_board_sized_crossing_street_and_site_inventory():
    assert len(NODES) >= 30
    assert len(EDGES) == 72
    assert len(BUILDING_SITES) == 46
    assert {site["zone"] for site in BUILDING_SITES.values()} == {1, 2, 3, 4}
    assert {zone: sum(site["zone"] == zone for site in BUILDING_SITES.values()) for zone in range(1, 5)} == {
        1: 12, 2: 12, 3: 9, 4: 13,
    }
    assert all({"crossing", "x", "y"} <= site.keys() for site in BUILDING_SITES.values())


def test_bus_topology_applies_reported_road_corrections_and_centers_c34():
    invalid_roads = {
        frozenset(("c1", "c6")), frozenset(("c3", "c9")),
        frozenset(("c25", "c27")), frozenset(("c30", "c32")),
        frozenset(("c35", "c36")),
        frozenset(("c19", "c22")), frozenset(("c14", "c20")),
        frozenset(("c13", "c15")), frozenset(("c3", "c6")),
        frozenset(("c3", "c2")), frozenset(("c2", "c5")),
        frozenset(("c10", "c8")), frozenset(("c4", "c13")),
        frozenset(("c6", "c10")),
    }
    required_roads = {
        frozenset(("c2", "c4")), frozenset(("c4", "c11")),
        frozenset(("c9", "c6")), frozenset(("c13", "c6")),
        frozenset(("c23", "c16")), frozenset(("c25", "c30")),
        frozenset(("c28", "c33")), frozenset(("c33", "c36")),
        frozenset(("c33", "c34")),
        frozenset(("c20", "c24")), frozenset(("c24", "c21")),
    }
    assert invalid_roads.isdisjoint(frozenset(edge) for edge in EDGES.values())
    assert required_roads <= {frozenset(edge) for edge in EDGES.values()}
    assert NODES["c34"] == {"x": 70.0, "y": 82.4}


def test_bus_serialization_exposes_public_scores_and_semantic_topology():
    validator = BusValidator()
    serialized = validator.serialize_for_screen(validator.initial_game_data())
    assert serialized["players"]["player_1"]["adjusted_score"] == 0
    assert serialized["players"]["player_1"]["route_ends"] == []
    assert serialized["topology"]["nodes"]["c4"]["station"] is True
    assert serialized["topology"]["edges"]["e1"] == ("c1", "c2")
    assert serialized["final_ranking"] == []


def test_bus_setup_offers_all_available_building_types_per_location():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    moves = validator.get_legal_moves(_state(data), data["current_player"])
    first_site = moves[0]["site_id"]
    assert {move["building_type"] for move in moves if move["site_id"] == first_site} == {"house", "office", "pub"}


def test_bus_initial_buildings_progress_clockwise_then_start_first_routes():
    validator = BusValidator()
    state = _state(validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"]))
    player_ids = list(state["game_data"]["players"])
    for placement_index in range(6):
        current = state["game_data"]["current_player"]
        state = _apply_first_move(validator, state, "setup_building")
        if placement_index < 5:
            expected_next = player_ids[(player_ids.index(current) + 1) % len(player_ids)]
            assert state["game_data"]["current_player"] == expected_next
    assert state["game_data"]["current_phase"] == "SETUP_FIRST_ROUTE_SEGMENTS"
    assert state["game_data"]["current_player"] == state["game_data"]["starting_player"]
    assert len(state["game_data"]["buildings"]) == 6
    building_ids = [building["building_id"] for building in state["game_data"]["buildings"].values()]
    assert len(building_ids) == len(set(building_ids))
    assert all(
        building_id == f"building-{site_id}"
        for site_id, building_id in zip(state["game_data"]["buildings"], building_ids)
    )
    assert all(
        building["owner_id"] in state["game_data"]["players"]
        for building in state["game_data"]["buildings"].values()
    )


def test_bus_initial_routes_reverse_for_second_segment_then_enter_action_selection():
    validator = BusValidator()
    state = _state(validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"]))
    for _ in range(6):
        state = _apply_first_move(validator, state, "setup_building")
    for _ in range(3):
        state = _apply_first_move(validator, state, "setup_first_route")
    player_ids = list(state["game_data"]["players"])
    expected_last = player_ids[(player_ids.index(state["game_data"]["starting_player"]) - 1) % len(player_ids)]
    assert state["game_data"]["current_player"] == expected_last
    for _ in range(3):
        state = _apply_first_move(validator, state, "setup_second_route")
    assert state["game_data"]["current_phase"] == "ACTION_SELECTION"
    assert state["game_data"]["round_number"] == 1


def test_bus_route_extension_rejects_parallel_street_when_empty_alternative_exists():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "RESOLVE_LINE_EXPANSION"
    data["current_player"] = "player_1"
    data["players"]["player_1"]["route_edges"] = ["e10"]
    data["players"]["player_2"]["route_edges"] = ["e1", "e10"]
    data["resolution"] = {"action_type": "line_expansion", "slot_index": 0, "player_id": "player_1", "remaining": 1}
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert not any(move["edge_id"] == "e1" and move.get("from_crossing") == "c1" for move in moves)


def test_bus_route_extension_allows_shared_end_parallel_exception():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "RESOLVE_LINE_EXPANSION"
    data["current_player"] = "player_1"
    data["players"]["player_1"]["route_edges"] = ["e78"]
    data["players"]["player_2"]["route_edges"] = ["e1"]
    data["resolution"] = {"action_type": "line_expansion", "slot_index": 0, "player_id": "player_1", "remaining": 1}
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert any(move["edge_id"] == "e1" and move.get("from_crossing") == "c2" for move in moves)


def test_bus_line_expansion_completes_when_player_has_no_line_markers_left():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "RESOLVE_LINE_EXPANSION"
    data["current_player"] = "player_1"
    data["players"]["player_1"]["route_edges"] = list(EDGES)[:MAX_LINE_MARKERS_PER_PLAYER]
    data["resolution"] = {"action_type": "line_expansion", "slot_index": 0, "player_id": "player_1", "remaining": 1}
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert moves == [{"move_id": "complete-line_expansion", "type": "complete_resolution", "player_id": "player_1"}]


@pytest.mark.parametrize(
    "action, phase",
    [
        ("line_expansion", "RESOLVE_LINE_EXPANSION"),
        ("buses", "RESOLVE_BUSES"),
        ("passengers", "RESOLVE_PASSENGERS"),
        ("buildings", "RESOLVE_BUILDINGS"),
        ("clock", "RESOLVE_CLOCK"),
        ("vrrooomm", "RESOLVE_VRROOMM"),
    ],
)
def test_bus_zero_remaining_resolution_only_exposes_completion_move(action, phase):
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = phase
    data["current_player"] = "player_1"
    data["resolution"] = {
        "action_type": action,
        "slot_index": 0,
        "resolution_index": 0,
        "player_id": "player_1",
        "remaining": 0,
    }
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert moves == [{"move_id": f"complete-{action}", "type": "complete_resolution", "player_id": "player_1"}]


def test_bus_third_parallel_line_requires_every_existing_line_to_end_at_crossing():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "RESOLVE_LINE_EXPANSION"
    data["current_player"] = "player_1"
    data["players"]["player_1"]["route_edges"] = ["e3"]
    data["players"]["player_2"]["route_edges"] = ["e7"]
    data["players"]["player_3"]["route_edges"] = ["e7", "e3"]
    data["resolution"] = {"action_type": "line_expansion", "slot_index": 0, "player_id": "player_1", "remaining": 1}
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert not any(move["edge_id"] == "e7" and move.get("from_crossing") == "c4" for move in moves)


def test_bus_third_parallel_line_allows_shared_end_when_every_line_ends_there():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "RESOLVE_LINE_EXPANSION"
    data["current_player"] = "player_1"
    data["players"]["player_1"]["route_edges"] = ["e7"]
    data["players"]["player_2"]["route_edges"] = ["e1"]
    data["players"]["player_3"]["route_edges"] = ["e1"]
    data["resolution"] = {"action_type": "line_expansion", "slot_index": 0, "player_id": "player_1", "remaining": 1}
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert any(move["edge_id"] == "e1" and move.get("from_crossing") == "c1" for move in moves)


def test_bus_loop_extension_retains_both_odd_degree_route_ends():
    validator = BusValidator()
    player = {"route_edges": ["e1", "e78", "e7"], "route_anchor": "c1"}
    assert validator._route_endpoints(player) == {"c1"}
    player["route_edges"].append("e10")
    validator._refresh_route_anchor(player, "c1")
    assert validator._route_endpoints(player) == {"c1", "c3"}
    assert player["route_anchor"] is None


def test_bus_serialization_exposes_route_ends_for_public_rule_verification():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["players"]["player_1"]["route_edges"] = ["e1", "e78"]
    serialized = validator.serialize_for_screen(data)
    assert serialized["players"]["player_1"]["route_ends"] == ["c1", "c4"]


def test_bus_action_selection_assigns_first_slot_and_requires_two_before_pass():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "ACTION_SELECTION"
    data["current_player"] = "player_1"
    state = _state(data)
    moves = validator.get_legal_moves(state, "player_1")
    assert not any(move["type"] == "pass_action_selection" for move in moves)
    selected = next(move for move in moves if move["action_type"] == "buses")
    state = {**state, **validator.apply_move(state, selected)}
    assert state["game_data"]["action_spaces"]["buses"] == ["player_1"]
    assert state["game_data"]["players"]["player_1"]["action_markers"] == 19


def test_bus_player_with_one_marker_can_select_once_then_becomes_inactive():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "ACTION_SELECTION",
        "current_player": "player_1",
        "action_spaces": {**data["action_spaces"], "clock": ["player_2"]},
    })
    data["players"]["player_1"]["action_markers"] = 1
    data["players"]["player_2"]["action_markers"] = 0
    data["players"]["player_3"]["action_markers"] = 0
    state = _state(data)
    move = next(move for move in validator.get_legal_moves(state, "player_1") if move["action_type"] == "buses")
    state = {**state, **validator.apply_move(state, move)}
    assert state["game_data"]["players"]["player_1"]["action_markers"] == 0
    assert state["game_data"]["current_phase"] == "RESOLVE_BUSES"
    assert state["game_data"]["current_player"] == "player_1"


def test_bus_action_selection_stops_at_the_six_printed_multi_action_slots():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "ACTION_SELECTION"
    data["current_player"] = "player_1"
    data["action_spaces"]["line_expansion"] = ["player_2"] * 6
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert not any(move.get("action_type") == "line_expansion" for move in moves)


def test_bus_player_with_all_five_buses_cannot_select_buses_action():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "ACTION_SELECTION"
    data["current_player"] = "player_1"
    data["players"]["player_1"]["buses"] = 5
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert not any(move.get("action_type") == "buses" for move in moves)


def test_bus_selected_actions_resolve_in_order_and_round_resets():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["current_phase"] = "ACTION_SELECTION"
    data["current_player"] = "player_1"
    data["starting_player"] = "player_1"
    state = _state(data)

    # Each player takes Passenger then Buses/Line Expansion, then passes.
    for _ in range(6):
        moves = validator.get_legal_moves(state, state["game_data"]["current_player"])
        preferred = next((move for move in moves if move.get("action_type") == "passengers"), None)
        state = {**state, **validator.apply_move(state, preferred or moves[0])}
    for _ in range(3):
        moves = validator.get_legal_moves(state, state["game_data"]["current_player"])
        passed = next(move for move in moves if move["type"] == "pass_action_selection")
        state = {**state, **validator.apply_move(state, passed)}

    assert state["game_data"]["current_phase"] == "RESOLVE_PASSENGERS"
    assert state["game_data"]["current_player"] == "player_1"
    assert state["game_data"]["resolution"]["remaining"] == 1
    state = _apply_first_move(validator, state, "place_passenger")
    assert state["game_data"]["current_player"] == "player_2"

    # Finish the remaining selected passenger actions; cleanup begins next round.
    for _ in range(5):
        moves = validator.get_legal_moves(state, state["game_data"]["current_player"])
        move = next(
            move
            for move in moves
            if move["type"] in {"place_passenger", "complete_resolution"}
        )
        state = {**state, **validator.apply_move(state, move)}
    assert state["game_data"]["current_phase"] == "ACTION_SELECTION"
    assert state["game_data"]["round_number"] == 1


def test_bus_vrrooomm_transports_connected_unsatisfied_passenger():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_VRROOMM",
        "current_player": "player_1",
        "clock": "office",
        "buildings": {
            "building_b_01": {"type": "house", "occupied_by": None},
            "building_d_01": {"type": "office", "occupied_by": None},
        },
        "passengers": {"passenger_test": "c1"},
        "resolution": {"action_type": "vrrooomm", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    data["players"]["player_1"]["route_edges"] = ["e1"]
    state = _state(data)
    state = _apply_first_move(validator, state, "transport")
    assert state["game_data"]["players"]["player_1"]["score"] == 1
    assert state["game_data"]["passengers"]["passenger_test"] == "building:building_d_01"


def test_bus_new_passengers_can_only_be_placed_at_designated_stations():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_PASSENGERS",
        "current_player": "player_1",
        "resolution": {"action_type": "passengers", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert {move["station"] for move in moves} == set(STATION_CROSSINGS)


def test_bus_building_actions_exclude_an_exhausted_building_type():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_BUILDINGS",
        "current_player": "player_1",
        "building_tiles_remaining": {"house": 0, "office": 1, "pub": 1},
        "resolution": {"action_type": "buildings", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert {move["building_type"] for move in moves} == {"office", "pub"}


def test_bus_building_zone_b_unlocks_only_after_every_a_location_is_filled():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_BUILDINGS",
        "current_player": "player_1",
        "buildings": {
            site_id: {"building_id": f"building-{site_id}", "type": "house", "occupied_by": None}
            for site_id, site in BUILDING_SITES.items() if site["zone"] == 1
        },
        "resolution": {"action_type": "buildings", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    moves = validator.get_legal_moves(_state(data), "player_1")
    assert moves
    assert {BUILDING_SITES[move["site_id"]]["zone"] for move in moves} == {2}


def test_bus_building_satisfies_passenger_already_at_its_crossing():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_BUILDINGS",
        "current_player": "player_1",
        "passengers": {"passenger_test": "c12"},
        "action_spaces": {**data["action_spaces"], "buildings": ["player_1"], "clock": ["player_2"]},
        "resolution": {"action_type": "buildings", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    state = _state(data)
    move = next(
        move for move in validator.get_legal_moves(state, "player_1")
        if move["site_id"] == "building_a_01" and move["building_type"] == "house"
    )
    state = {**state, **validator.apply_move(state, move)}
    assert state["game_data"]["passengers"]["passenger_test"] == "building:building_a_01"
    assert state["game_data"]["buildings"]["building_a_01"]["occupied_by"] == "passenger_test"


def test_bus_clock_change_releases_passengers_from_no_longer_matching_buildings():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_CLOCK",
        "current_player": "player_1",
        "clock": "house",
        "buildings": {
            "building_a_01": {
                "building_id": "building-building_a_01",
                "type": "house",
                "occupied_by": "passenger_test",
            },
        },
        "passengers": {"passenger_test": "building:building_a_01"},
        "action_spaces": {**data["action_spaces"], "clock": ["player_1"]},
        "resolution": {"action_type": "clock", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    state = _apply_first_move(validator, _state(data), "clock_advance")
    assert state["game_data"]["clock"] == "office"
    assert state["game_data"]["passengers"]["passenger_test"] == "c12"
    assert state["game_data"]["buildings"]["building_a_01"]["occupied_by"] is None


def test_bus_vrrooomm_resolution_uses_own_bus_count():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["players"]["player_1"]["buses"] = 3
    data["action_spaces"]["vrrooomm"] = ["player_1"]
    validator._begin_next_resolution(data, ["player_1", "player_2", "player_3"])
    assert data["current_phase"] == "RESOLVE_VRROOMM"
    assert data["resolution"]["remaining"] == 3


def test_bus_five_player_line_expansion_receives_its_extra_placement():
    validator = BusValidator()
    player_ids = [f"player_{number}" for number in range(1, 6)]
    data = validator.initial_game_data(player_ids=player_ids)
    data["action_spaces"]["line_expansion"] = ["player_1"]
    validator._begin_next_resolution(data, player_ids)
    assert data["current_phase"] == "RESOLVE_LINE_EXPANSION"
    assert data["resolution"]["remaining"] == 2


def test_bus_purchase_updates_following_passenger_quantity_in_same_round():
    validator = BusValidator()
    player_ids = ["player_1", "player_2", "player_3"]
    data = validator.initial_game_data(player_ids=player_ids)
    data["action_spaces"]["buses"] = ["player_1"]
    data["action_spaces"]["passengers"] = ["player_2"]
    validator._begin_next_resolution(data, player_ids)
    state = _state(data)
    state = _apply_first_move(validator, state, "buy_bus")
    assert state["game_data"]["current_phase"] == "RESOLVE_PASSENGERS"
    assert state["game_data"]["resolution"]["remaining"] == 2


def test_bus_purchase_updates_following_building_quantity_in_same_round():
    validator = BusValidator()
    player_ids = ["player_1", "player_2", "player_3"]
    data = validator.initial_game_data(player_ids=player_ids)
    data["action_spaces"]["buses"] = ["player_1"]
    data["action_spaces"]["buildings"] = ["player_2"]
    validator._begin_next_resolution(data, player_ids)
    state = _state(data)
    state = _apply_first_move(validator, state, "buy_bus")
    assert state["game_data"]["current_phase"] == "RESOLVE_BUILDINGS"
    assert state["game_data"]["resolution"]["remaining"] == 2


def test_bus_reverse_resolved_actions_keep_their_physical_slot_quantities():
    validator = BusValidator()
    player_ids = ["player_1", "player_2", "player_3"]
    data = validator.initial_game_data(player_ids=player_ids)
    data["players"]["player_1"]["buses"] = 3
    data["action_spaces"]["line_expansion"] = ["player_1", "player_2"]
    validator._begin_next_resolution(data, player_ids)
    # B resolves before A, but physical B gets one fewer placement.
    assert data["resolution"] == {
        "action_type": "line_expansion",
        "slot_index": 1,
        "resolution_index": 0,
        "player_id": "player_2",
        "remaining": 2,
    }
    data["resolution"]["remaining"] = 0
    validator._begin_next_resolution(data, player_ids)
    assert data["resolution"]["player_id"] == "player_1"
    assert data["resolution"]["slot_index"] == 0
    assert data["resolution"]["remaining"] == 3


def test_bus_last_time_stone_stops_resolution_immediately():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_CLOCK",
        "current_player": "player_1",
        "time_stones_remaining": 1,
        "resolution": {"action_type": "clock", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })
    state = _state(data)
    state = _apply_first_move(validator, state, "clock_stop")
    assert state["game_data"]["game_over"] is True
    assert state["game_data"]["terminal_reason"] == "clock_rupture"


def test_bus_stopping_clock_keeps_current_building_type_and_claims_one_stone():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data.update({
        "current_phase": "RESOLVE_CLOCK",
        "current_player": "player_1",
        "clock": "office",
        "time_stones_remaining": 4,
        "action_spaces": {**data["action_spaces"], "clock": ["player_1"]},
        "resolution": {"action_type": "clock", "slot_index": 0, "player_id": "player_1", "remaining": 1},
    })

    state = _apply_first_move(validator, _state(data), "clock_stop")

    assert state["game_data"]["clock"] == "office"
    assert state["game_data"]["time_stones_remaining"] == 3
    assert state["game_data"]["players"]["player_1"]["time_stones"] == 1


def test_bus_unselected_clock_advances_during_resolution_scheduling():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["action_spaces"]["starting_player"] = ["player_1"]
    validator._begin_next_resolution(data, ["player_1", "player_2", "player_3"])
    assert data["clock"] == "office"
    assert data["current_phase"] == "RESOLVE_STARTING_PLAYER"


def test_bus_only_one_player_with_markers_ends_after_round():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["players"]["player_2"]["action_markers"] = 0
    data["players"]["player_3"]["action_markers"] = 0
    validator._complete_round(data, ["player_1", "player_2", "player_3"])
    assert data["game_over"] is True
    assert data["terminal_reason"] == "action_markers_exhausted"


def test_bus_new_round_skips_starting_player_with_no_markers_left():
    """Regression: a new round must not hand the turn to a marker-exhausted
    starting player, which previously stalled the game with no legal moves."""
    validator = BusValidator()
    player_ids = ["player_1", "player_2", "player_3"]
    data = validator.initial_game_data(player_ids=player_ids)
    data["players"]["player_1"]["action_markers"] = 0
    data["next_starting_player"] = "player_1"
    validator._complete_round(data, player_ids)
    assert data["game_over"] is False
    assert data["starting_player"] == "player_1"
    assert data["current_player"] == "player_2"
    assert validator.get_legal_moves(_state(data), "player_2")


def test_bus_final_ranking_uses_adjusted_score_then_time_stones_then_stack_order():
    validator = BusValidator()
    data = validator.initial_game_data(player_ids=["player_1", "player_2", "player_3"])
    data["game_over"] = True
    data["players"]["player_1"].update(score=7, time_stones=1, score_stack_order=4)
    data["players"]["player_2"].update(score=6, time_stones=0, score_stack_order=1)
    data["players"]["player_3"].update(score=6, time_stones=0, score_stack_order=0)
    # All adjusted scores are six. Player 1 wins the first tie breaker.
    assert validator.check_win(_state(data)) == "player_1"
    assert validator.serialize_for_screen(data)["final_ranking"] == ["player_1", "player_3", "player_2"]