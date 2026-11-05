"""Extended tests for Fields of Fire (Deluxe) validator."""

from app.games.fields_of_fire.validator import FieldsOfFireValidator
from app.games.fields_of_fire.terrain import terrain_card, get_card, get_deck, list_decks


def test_weapon_stats():
    v = FieldsOfFireValidator()
    stats = v.get_weapon_stats("mg")
    assert stats["range"] == 6
    assert stats["vof_rating"] == "B"
    assert stats["ammo_type"] == "mg"


def test_calculate_vof_rating():
    v = FieldsOfFireValidator()
    rating = v.calculate_vof_rating("rifle", 3, concentrated=True)
    assert rating in ("A", "B", "C", "D")


def test_vehicle_stats():
    v = FieldsOfFireValidator()
    stats = v.get_vehicle_stats("m113")
    assert stats["armor"] == 2
    assert stats["capacity"] == 12


def test_resolve_vof_vs_vehicle():
    v = FieldsOfFireValidator()
    result = v.resolve_vof_vs_vehicle("A", "m48")
    assert result in ("destroyed", "immobilized", "suppressed", "no_effect")


def test_cover_modifier():
    v = FieldsOfFireValidator()
    mod = v.get_cover_modifier(3)
    assert mod == 2
    mod = v.get_cover_modifier(0)
    assert mod == -1


def test_command_radius():
    v = FieldsOfFireValidator()
    assert v.get_command_radius("bn_hq_1") == 3
    assert v.get_command_radius("co_hq_1") == 2
    assert v.get_command_radius("plt_hq_1") == 1


def test_activation_sequence():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    seq = v.get_activation_sequence(gd)
    assert len(seq) > 0
    assert seq[0] == "bn_hq_1"


def test_los_same_card():
    v = FieldsOfFireValidator()
    ok, reason = v.has_los("N01", "N01")
    assert ok is True
    assert reason == "same_card"


def test_movement_cost():
    v = FieldsOfFireValidator()
    cost = v.calculate_movement_cost(0, 5)
    assert cost > 0
    cost = v.calculate_movement_cost(0, 0)
    assert cost == 0


def test_smoke_placement():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    smoke = v.place_smoke_marker(0, duration=3, game_data=gd)
    assert smoke["position"] == 0
    assert smoke["duration"] == 3
    assert v.is_smoke_at(0, gd) is True


def test_smoke_dissipation():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.place_smoke_marker(0, duration=1, game_data=gd)
    dissipated = v.dissipate_smoke(gd)
    assert dissipated == 1
    assert v.is_smoke_at(0, gd) is False


def test_vof_placement():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    vof = v.place_vof_marker(0, "A", game_data=gd)
    assert vof["rating"] == "A"
    assert v.get_vof_at(0, gd) is not None


def test_vof_resolution():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.place_vof_marker(0, "B", game_data=gd)
    result = v.resolve_vof(0, game_data=gd)
    assert result["rating"] == "B"
    assert result["hit_modifier"] == 2


def test_enemy_contact():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    pc = v.place_pc_marker(0, game_data=gd)
    assert pc["position"] == 0
    result = v.resolve_pc_contact("pc_1", "contact", game_data=gd)
    assert result["resolved"] is True
    assert v.get_contact_level(gd) == "contact"


def test_enemy_activity():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["contact_level"] = "contact"
    result = v.enemy_activity_check(gd)
    assert "enemy_move" in result["actions"]


def test_grenade_types():
    v = FieldsOfFireValidator()
    types = v.get_grenade_types()
    assert "frag" in types
    assert "smoke" in types


def test_fire_mission_types():
    v = FieldsOfFireValidator()
    types = v.get_fire_mission_types()
    assert "HE" in types
    assert "smoke_wp" in types


def test_register_target():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.register_target(5, game_data=gd)
    assert v.is_target_registered(5, gd) is True
    assert v.is_target_registered(3, gd) is False


def test_campaign_experience():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    exp = v.gain_experience(10, game_data=gd)
    assert exp == 10
    assert v.get_experience(gd) == 10


def test_skill_acquisition():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.gain_experience(5, game_data=gd)
    result = v.spend_experience("leadership", 1, game_data=gd)
    assert result is True
    assert v.has_skill("leadership", gd) is True


def test_urban_combat():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.enter_building("squad_1", 0, game_data=gd)
    assert v.is_in_building("squad_1", gd) is True
    mod = v.urban_combat_modifier(0, gd)
    assert mod >= 0


def test_limited_visibility():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.set_limited_visibility(True, game_data=gd)
    assert v.is_night(gd) is True
    vrange = v.los_range_limited(gd)
    assert vrange == 1


def test_night_observation():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.set_limited_visibility(True, game_data=gd)
    v.set_night_observation(True, game_data=gd)
    vrange = v.los_range_limited(gd)
    assert vrange == 2


def test_vehicle_transport():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["company"]["vehicles"] = [{"id": "m113_1", "type": "m113", "position": None, "embarked": []}]
    result = v.embark_unit("squad_1", "m113_1", gd)
    assert result is True
    cap = v.vehicle_transport_capacity("m113_1", gd)
    assert cap["embarked"] == 1


def test_helicopter_transport():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["company"]["helicopters"] = [{"id": "uh1_1", "type": "uh1", "position": None, "loaded_units": [], "capacity": 8}]
    result = v.load_helicopter("uh1_1", ["squad_1", "squad_2"], gd)
    assert result["loaded"] is True
    assert result["total_loaded"] == 2


def test_assault_planning():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    gd["landing_zones"] = [0]
    result = v.plan_air_assault("uh1_1", 0, ["squad_1"], gd)
    assert result["planned"] is True
    pending = v.get_pending_assaults(gd)
    assert len(pending) == 1


def test_mine_placement():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    mine = v.place_mine_marker(0, "ap", game_data=gd)
    assert mine["mine_type"] == "ap"
    assert v.is_mine_at(0, gd) is True


def test_indirect_fire():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    v.register_target(5, game_data=gd)
    result = v.resolve_fire_mission("HE", 5, game_data=gd)
    assert result["resolved"] is True
    assert result["effect"] == "high_explosive"


def test_can_communicate_same_card():
    v = FieldsOfFireValidator()
    u1 = {"position": 0}
    u2 = {"position": 0}
    assert v.can_communicate(u1, u2) is True


def test_can_communicate_adjacent():
    v = FieldsOfFireValidator()
    u1 = {"position": 0}
    u2 = {"position": 1}
    assert v.can_communicate(u1, u2) is True


def test_radio_communication():
    v = FieldsOfFireValidator()
    gd = v.initial_game_data()
    u1 = {"position": 0, "type": "hq"}
    u2 = {"position": 5, "type": "squad"}
    assert v.can_communicate(u1, u2, game_data=gd) is True
