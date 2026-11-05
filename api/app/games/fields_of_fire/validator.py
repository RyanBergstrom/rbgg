from __future__ import annotations
import os
import json

from typing import Any

from app.core.legal_move_interface import LegalMoveValidator, IllegalMoveError
from app.games.fields_of_fire.terrain import terrain_card

PHASES = [
    "setup",
    "friendly_higher_hq_event",
    "friendly_command",
    "enemy_activity",
    "mutual_capture_retreat",
    "at_combat_vehicle_movement",
    "mutual_combat",
    "clean_up",
    "game_over",
]


class FieldsOfFireValidator(LegalMoveValidator):
    """Validator for Fields of Fire (Deluxe) — incremental implementation."""

    def __init__(self) -> None:
        super().__init__()

    def initial_game_data(self, scenario_id=None):
        units = []
        units.append({"id": "bn_hq_1", "type": "hq", "level": "bn", "position": None})
        units.append({"id": "co_hq_1", "type": "hq", "level": "co", "position": None})
        units.append({"id": "co_staff_1", "type": "staff", "position": None})
        for i in range(3):
            units.append({"id": f"plt_hq_{i+1}", "type": "hq", "level": "plt", "position": None})
        for i in range(9):
            units.append({"id": f"squad_{i+1}", "type": "squad", "position": None})
        for i in range(3):
            units.append({"id": f"wpn_team_{i+1}", "type": "weapon_team", "position": None, "weapon": "mg"})
        for i in range(2):
            units.append({"id": f"mortar_{i+1}", "type": "mortar_team", "position": None, "weapon": "mortar"})
        for i in range(2):
            units.append({"id": f"at_team_{i+1}", "type": "at_team", "position": None, "weapon": "rcl"})
        base = {
            "game": "fields_of_fire",
            "edition": "deluxe",
            "phase": "setup",
            "current_player": "player_1",
            "turn": 1,
            "players": {"player_1": {"id": "player_1", "name": "Commander"}},
            "company": {
                "hq": None,
                "platoons": [],
                "assets": [],
                "staff": [],
                "units": units,
                "weapons_teams": [],
                "runners": [],
                "casualties": [],
                "lats": [],
                "vehicles": [{"id": "m113_1", "type": "apc", "position": None}],
                "helicopters": [{"id": "uh1_1", "type": "uh1", "position": None}],
                "landing_zones": [],
                "assault_waves": [],
                "command": {
                    "bn_hq": "bn_hq_1",
                    "co_hq": "co_hq_1",
                    "plt_hqs": [f"plt_hq_{i+1}" for i in range(3)],
                    "co_staff": ["co_staff_1"],
                    "activated": [],
                    "commands_pool": 0,
                    "command_draw": []
                },
                "networks": {"radios": [{"id": "scr536_co_tac", "type": "scr536", "net": "co_tac", "damaged": False}], "phones": [], "runners": []},
                "ammo": {"mg": 6, "mtr": 4, "rcl": 3, "rkt": 2, "demo": 2, "f": 2},
                "experience": 0,
                "experience_points": 0,
                "skills": [],
                "replacements": 0,
                "campaign_missions_completed": [],
                "campaign_won": False
            },
            "map": {"rows": 3, "cols": 4, "cards": [None] * 12},
            "markers": [],
            "enemy": [],
            "enemy_packages": [],
            "pc_markers": [],
            "contact_level": "no_contact",
            "visibility": {"limited": False, "illumination": None, "night_observation": False},
            "vof_markers": [],
            "pdf_markers": [],
            "smoke_markers": [],
            "urban": {"buildings": [], "breached": [], "rooftops": [], "barricades": []},
            "rng_seed": 0,
            "registered_targets": [],
            "campaign": {"missions_completed": [], "experience": 0, "replacements_available": 0},
            "deployment_zones": [],
            "scenario_id": scenario_id,
        }
        # Apply scenario overrides if scenario_id provided
        if scenario_id:
            scenario = self.get_scenario(scenario_id)
            if scenario:
                base["scenario_id"] = scenario_id
                # Override map layout
                map_layout = scenario.get("map_layout", {})
                if map_layout.get("rows"):
                    base["map"]["rows"] = map_layout["rows"]
                if map_layout.get("cols"):
                    base["map"]["cols"] = map_layout["cols"]
                base["map"]["card_layout"] = map_layout.get("card_layout")
                if map_layout.get("rows") and map_layout.get("cols"):
                    card_layout = map_layout.get("card_layout")
                    if card_layout and isinstance(card_layout, list):
                        # Support both old format (list of card IDs) and new format (list of {row,col,id,...})
                        cards = [None] * (map_layout["rows"] * map_layout["cols"])
                        if any(isinstance(i, dict) for i in card_layout):
                            for item in card_layout:
                                if isinstance(item, dict):
                                    r = item.get("row")
                                    c = item.get("col")
                                    cid = item.get("id")
                                    if r is not None and c is not None:
                                        idx = int(r) * map_layout["cols"] + int(c)
                                        if 0 <= idx < len(cards):
                                            cards[idx] = cid
                            base["map"]["cards"] = cards
                            base["deployment_zones"] = []
                            for item in card_layout:
                                if isinstance(item, dict) and item.get("deployment_zone"):
                                    r = item.get("row")
                                    c = item.get("col")
                                    if r is not None and c is not None:
                                        idx = int(r) * map_layout["cols"] + int(c)
                                        base["deployment_zones"].append(idx)
                        else:
                            base["map"]["cards"] = card_layout[:map_layout["rows"] * map_layout["cols"]]
                            while len(base["map"]["cards"]) < map_layout["rows"] * map_layout["cols"]:
                                base["map"]["cards"].append(None)
                    else:
                        base["map"]["cards"] = [None] * (map_layout["rows"] * map_layout["cols"])
                # Override deployment zones
                base["deployment_zones"] = scenario.get("deployment_zones", [])
                # Override victory conditions
                base["victory_conditions"] = scenario.get("victory_conditions")
                # Override experience reward
                base["experience_reward"] = scenario.get("experience_reward", 0)
        return base

    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        gd = state.get("game_data", {})
        phase = gd.get("phase")
        # Also check top-level phase if not in game_data (backward compatibility)
        if phase is None:
            phase = state.get("phase")
        mtype = move.get("type")
        if mtype == "start_mission" and phase == "setup":
            scenario_id = move.get("scenario_id")
            if scenario_id is not None:
                if not isinstance(scenario_id, str):
                    return False
                valid, reason = self.validate_scenario(scenario_id)
                if not valid:
                    return False
            # Check setup completion
            complete, reason = self.is_setup_complete(gd)
            if not complete:
                return False
            return True
        if mtype == "select_scenario" and phase == "setup":
            scenario_id = move.get("scenario_id")
            if not isinstance(scenario_id, str):
                return False
            valid, reason = self.validate_scenario(scenario_id)
            return valid
        if mtype == "lay_out_map" and phase == "setup":
            cards = move.get("cards")
            expected = gd.get("map", {}).get("rows", 0) * gd.get("map", {}).get("cols", 0)
            return isinstance(cards, list) and len(cards) == expected
        if mtype == "advance_phase":
            if phase in PHASES and phase not in ("game_over",):
                next_phase = move.get("next_phase")
                if isinstance(next_phase, str) and next_phase in PHASES:
                    return True
            return False
        if mtype == "place_vehicle" and phase in ("setup", "friendly_command"):
            return isinstance(move.get("vehicle_id"), str) and isinstance(move.get("position"), int)
        if mtype == "helicopter_assault" and phase in ("setup", "friendly_command"):
            return True
        if mtype == "resolve_pc" and phase in ("enemy_activity", "friendly_higher_hq_event"):
            return isinstance(move.get("pc_id"), str)
        if mtype == "enemy_activity_check" and phase == "enemy_activity":
            return True
        if mtype == "place_enemy" and phase in ("setup", "enemy_activity"):
            enemy_id = move.get("enemy_id")
            position = move.get("position")
            if not isinstance(enemy_id, str) or not isinstance(position, int):
                return False
            map_data = gd.get("map", {})
            cards = map_data.get("cards", [])
            return 0 <= position < len(cards)
            return isinstance(move.get("mission_type"), str)
        if mtype == "grenade_attack" and phase == "mutual_combat":
            return True
        if mtype == "concentrate_fire" and phase == "mutual_combat":
            return True
        if mtype == "demolition_charge" and phase in ("friendly_command", "mutual_combat"):
            return True
        if mtype == "place_mine" and phase in ("friendly_command", "mutual_combat"):
            return isinstance(move.get("position"), int)
        if mtype == "flamethrower_attack" and phase == "mutual_combat":
            return True
        if mtype == "sniper" and phase == "mutual_combat":
            return True
        if mtype == "register_target" and phase == "friendly_command":
            return isinstance(move.get("position"), int)
        if mtype == "activate_hq" and phase == "friendly_command":
            hq_id = move.get("hq_id")
            return isinstance(hq_id, str)
        if mtype == "draw_commands" and phase == "friendly_command":
            return True
        if mtype == "spend_command" and phase == "friendly_command":
            return isinstance(move.get("amount"), int) and move.get("amount", 0) > 0
        if mtype == "exhort" and phase == "friendly_command":
            return True
        if mtype == "reconstitute" and phase == "friendly_command":
            return True
        if mtype == "create_runner" and phase == "friendly_command":
            return True
        if mtype == "dispatch_runner" and phase == "friendly_command":
            return True
        if mtype == "deploy_pyrotechnic" and phase == "friendly_command":
            return True
        if mtype == "designate_tactical_control" and phase == "friendly_command":
            return True
        if mtype == "move_action" and phase == "friendly_command":
            return True
        if mtype == "open_fire" and phase == "friendly_command":
            return True
        if mtype == "place_vof" and phase in ("friendly_command", "mutual_combat"):
            position = move.get("position")
            rating = move.get("rating")
            return isinstance(position, int) and isinstance(rating, str)
        if mtype == "place_pdf" and phase in ("friendly_command", "mutual_combat"):
            position = move.get("position")
            direction = move.get("direction")
            return isinstance(position, int) and isinstance(direction, str)
        if mtype == "place_smoke" and phase in ("friendly_command", "mutual_combat"):
            return isinstance(move.get("position"), int)
        if mtype == "fire" and phase == "mutual_combat":
            return True
        if mtype == "rally" and phase in ("friendly_command", "mutual_combat"):
            return True
        if mtype == "move_unit" and phase in ("friendly_command", "mutual_combat"):
            unit_id = move.get("unit_id")
            from_pos = move.get("from_position")
            to_pos = move.get("to_position")
            if not isinstance(unit_id, str) or not isinstance(from_pos, int) or not isinstance(to_pos, int):
                return False
            map_data = gd.get("map", {})
            cards = map_data.get("cards", [])
            if not (0 <= from_pos < len(cards) and 0 <= to_pos < len(cards)):
                return False
            # Stacking limit: destination card must have < 10 units
            units_on_dest = [u for u in gd.get("company", {}).get("units", []) if u.get("position") == to_pos]
            if len(units_on_dest) >= 10:
                return False
            # Terrain trafficability for vehicles
            unit_type = None
            for u in gd.get("company", {}).get("units", []):
                if u.get("id") == unit_id:
                    unit_type = u.get("type", "")
                    break
            is_vehicle = unit_type and ("vehicle" in unit_type.lower() or unit_type in ("apc", "tank", "truck"))
            if is_vehicle:
                card_id = cards[to_pos] if to_pos < len(cards) else None
                if card_id:
                    from app.games.fields_of_fire.terrain import terrain_card, get_card
                    card_data = get_card(card_id)
                    if card_data:
                        tc = terrain_card(card_data.get("terrain_type", "open_field"), card_id)
                        traffic = tc.get("trafficability", "good")
                        if traffic not in ("good", "fair"):
                            return False
            # Verify unit exists at from_pos
            unit_at_from = [u for u in gd.get("company", {}).get("units", []) if u.get("id") == unit_id]
            if unit_at_from and unit_at_from[0].get("position") != from_pos:
                return False
            return True
        if mtype == "place_unit" and phase in ("setup", "friendly_command"):
            unit_id = move.get("unit_id")
            position = move.get("position")
            if not isinstance(unit_id, str) or not isinstance(position, int):
                return False
            map_data = gd.get("map", {})
            cards = map_data.get("cards", [])
            if not (0 <= position < len(cards)):
                return False
            units_on_card = [u for u in gd.get("company", {}).get("units", []) if u.get("position") == position]
            if len(units_on_card) >= 10:
                return False
            # Terrain trafficability: vehicles require good/fair trafficability
            unit_type = None
            for u in gd.get("company", {}).get("units", []):
                if u.get("id") == unit_id:
                    unit_type = u.get("type", "")
                    break
            # Check vehicles list too
            is_vehicle = False
            for v in gd.get("company", {}).get("vehicles", []):
                if v.get("id") == unit_id:
                    is_vehicle = True
                    break
            if is_vehicle or (unit_type and "vehicle" in unit_type.lower()):
                from app.games.fields_of_fire.terrain import terrain_card, get_card
                card_id = cards[position] if position < len(cards) else None
                if card_id:
                    card_data = get_card(card_id)
                    if card_data:
                        tc = terrain_card(card_data.get("terrain_type", "open_field"), card_id)
                        traffic = tc.get("trafficability", "good")
                        if traffic not in ("good", "fair"):
                            return False
            # Deployment zone restriction during setup
            if phase == "setup":
                zones = gd.get("deployment_zones", [])
                if zones:
                    if position not in zones:
                        return False
            return True
        if mtype == "place_enemy" and phase in ("setup", "enemy_activity"):
            enemy_id = move.get("enemy_id")
            position = move.get("position")
            if not isinstance(enemy_id, str) or not isinstance(position, int):
                return False
            map_data = gd.get("map", {})
            cards = map_data.get("cards", [])
            return 0 <= position < len(cards)
        if mtype == "place_marker" and phase in ("setup", "friendly_command", "mutual_combat", "friendly_higher_hq_event"):
            return isinstance(move.get("marker"), str) and isinstance(move.get("position"), int)
        if mtype == "amphibious_assault" and phase in ("setup", "friendly_command"):
            return True
        if mtype == "at_fire" and phase in ("friendly_command", "mutual_combat", "at_combat_vehicle_movement"):
            return True
        if mtype == "barricade" and phase in ("friendly_command", "mutual_combat"):
            return isinstance(move.get("position"), int)
        if mtype == "breach_building" and phase in ("friendly_command", "mutual_combat"):
            return isinstance(move.get("position"), int)
        if mtype == "call_fire_mission" and phase in ("friendly_command", "mutual_combat"):
            return isinstance(move.get("mission_type"), str)
        if mtype == "disembark" and phase in ("friendly_command", "at_combat_vehicle_movement"):
            return True
        if mtype == "embark" and phase in ("friendly_command", "at_combat_vehicle_movement"):
            return True
        if mtype == "end_mission" and phase in ("clean_up", "friendly_command"):
            return True
        if mtype == "enter_building" and phase in ("friendly_command", "mutual_combat"):
            return isinstance(move.get("position"), int)
        if mtype == "gain_experience" and phase == "clean_up":
            return isinstance(move.get("amount"), int) and move.get("amount", 0) > 0
        if mtype == "land_helicopter" and phase in ("setup", "friendly_command"):
            return isinstance(move.get("position"), int)
        if mtype == "load_helicopter" and phase in ("setup", "friendly_command"):
            return True
        if mtype == "move_vehicle" and phase in ("friendly_command", "at_combat_vehicle_movement", "mutual_combat"):
            vehicle_id = move.get("vehicle_id")
            from_pos = move.get("from_position")
            to_pos = move.get("to_position")
            if not isinstance(vehicle_id, str) or not isinstance(from_pos, int) or not isinstance(to_pos, int):
                return False
            map_data = gd.get("map", {})
            cards = map_data.get("cards", [])
            return 0 <= from_pos < len(cards) and 0 <= to_pos < len(cards)
        if mtype == "place_illumination" and phase in ("friendly_command", "mutual_combat", "friendly_higher_hq_event"):
            return isinstance(move.get("position"), int)
        if mtype == "plan_assault" and phase in ("setup", "friendly_command"):
            return True
        if mtype == "request_replacements" and phase == "clean_up":
            return True
        if mtype == "set_visibility" and phase in ("friendly_higher_hq_event", "friendly_command"):
            return isinstance(move.get("limited"), bool)
        if mtype == "spend_experience" and phase == "clean_up":
            return isinstance(move.get("skill"), str)
        if mtype == "urban_combat" and phase == "mutual_combat":
            return True
        return False








    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        gd = state.get("game_data", {})
        phase = gd.get("phase")
        if phase == "setup":
            rows = gd.get("map", {}).get("rows", 0)
            cols = gd.get("map", {}).get("cols", 0)
            moves = [
                {"move_id": "start_mission", "type": "start_mission", "player_id": player_id},
            ]
            # Only offer lay_out_map if map cards are not already set
            cards = gd.get("map", {}).get("cards", [])
            if not cards or all(c is None for c in cards):
                moves.append({"move_id": "lay_out_map", "type": "lay_out_map", "player_id": player_id,
                             "cards": [None] * (rows * cols)})
            company = gd.get("company", {})
            for unit in company.get("units", []):
                if unit.get("position") is None:
                    moves.append({"move_id": f"place_unit_{unit.get('id')}", "type": "place_unit", 
                                 "player_id": player_id, "unit_id": unit.get("id"), "position": 0})
            for vehicle in company.get("vehicles", []):
                if vehicle.get("position") is None:
                    moves.append({"move_id": f"place_vehicle_{vehicle.get('id')}", "type": "place_vehicle", 
                                 "player_id": player_id, "vehicle_id": vehicle.get("id"), "position": 0})
            moves.append({"move_id": "place_pc", "type": "place_enemy", "player_id": player_id, "enemy_id": "pc_1", "position": 0})
            return moves
        if phase == "friendly_higher_hq_event":
            moves = [{"move_id": "advance_phase", "type": "advance_phase", "player_id": player_id,
                      "next_phase": self._next_phase(phase)}]
            moves.append({"move_id": "place_marker", "type": "place_marker", "player_id": player_id,
                          "marker": "exposed", "position": 0})
            moves.append({"move_id": "resolve_pc", "type": "resolve_pc", "player_id": player_id, "pc_id": "pc_1"})
            moves.append({"move_id": "set_visibility", "type": "set_visibility", "player_id": player_id, "limited": False})
            moves.append({"move_id": "helicopter_assault", "type": "helicopter_assault", "player_id": player_id})
            return moves
        if phase == "friendly_command":
            moves = [{"move_id": "advance_phase", "type": "advance_phase", "player_id": player_id,
                      "next_phase": self._next_phase(phase)}]
            cmd = gd.get("company", {}).get("command", {})
            for hq_id in ([cmd.get("bn_hq")] if cmd.get("bn_hq") else []) + ([cmd.get("co_hq")] if cmd.get("co_hq") else []) + cmd.get("plt_hqs", []) + cmd.get("co_staff", []):
                if hq_id and hq_id not in cmd.get("activated", []):
                    moves.append({"move_id": f"activate_{hq_id}", "type": "activate_hq", "player_id": player_id, "hq_id": hq_id})
            if cmd.get("activated"):
                moves.append({"move_id": "draw_commands", "type": "draw_commands", "player_id": player_id})
                if cmd.get("commands_pool", 0) > 0:
                    moves.append({"move_id": "spend_command", "type": "spend_command", "player_id": player_id, "amount": 1})
                    moves.append({"move_id": "exhort", "type": "exhort", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "reconstitute", "type": "reconstitute", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "create_runner", "type": "create_runner", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "dispatch_runner", "type": "dispatch_runner", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "deploy_pyrotechnic", "type": "deploy_pyrotechnic", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "designate_tactical_control", "type": "designate_tactical_control", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "move_action", "type": "move_action", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "rally", "type": "rally", "player_id": player_id, "cost": 1})
                    moves.append({"move_id": "open_fire", "type": "open_fire", "player_id": player_id, "cost": 1})
            moves.append({"move_id": "place_marker", "type": "place_marker", "player_id": player_id,
                          "marker": "exposed", "position": 0})
            moves.append({"move_id": "place_illumination", "type": "place_illumination", "player_id": player_id, "position": 0})
            moves.append({"move_id": "place_vehicle", "type": "place_vehicle", "player_id": player_id, "vehicle_id": "m113_1", "position": 0})
            moves.append({"move_id": "helicopter_assault", "type": "helicopter_assault", "player_id": player_id})
            moves.append({"move_id": "plan_assault", "type": "plan_assault", "player_id": player_id})
            moves.append({"move_id": "load_helicopter", "type": "load_helicopter", "player_id": player_id})
            moves.append({"move_id": "land_helicopter", "type": "land_helicopter", "player_id": player_id, "position": 0})
            moves.append({"move_id": "amphibious_assault", "type": "amphibious_assault", "player_id": player_id})
            moves.append({"move_id": "gain_experience", "type": "gain_experience", "player_id": player_id, "amount": 1})
            moves.append({"move_id": "spend_experience", "type": "spend_experience", "player_id": player_id, "skill": "leadership"})
            moves.append({"move_id": "enter_building", "type": "enter_building", "player_id": player_id, "position": 0})
            moves.append({"move_id": "breach_building", "type": "breach_building", "player_id": player_id, "position": 0})
            moves.append({"move_id": "barricade", "type": "barricade", "player_id": player_id, "position": 0})
            return moves
        if phase == "enemy_activity":
            moves = [{"move_id": "advance_phase", "type": "advance_phase", "player_id": player_id,
                      "next_phase": self._next_phase(phase)}]
            moves.append({"move_id": "enemy_activity_check", "type": "enemy_activity_check", "player_id": player_id})
            moves.append({"move_id": "resolve_pc", "type": "resolve_pc", "player_id": player_id, "pc_id": "pc_1", "contact_level": "contact"})
            return moves
        if phase in PHASES and phase not in ("setup", "game_over", "enemy_activity"):
            moves = [{"move_id": "advance_phase", "type": "advance_phase", "player_id": player_id,
                      "next_phase": self._next_phase(phase)}]
            moves.append({"move_id": "place_marker", "type": "place_marker", "player_id": player_id,
                          "marker": "exposed", "position": 0})
            for unit in gd.get("company", {}).get("units", []):
                if unit.get("position") is not None:
                    moves.append({"move_id": f"move_{unit.get('id')}", "type": "move_unit", "player_id": player_id,
                                 "unit_id": unit.get("id"), "from_position": unit.get("position"), "to_position": unit.get("position")})
            for vehicle in gd.get("company", {}).get("vehicles", []):
                if vehicle.get("position") is not None:
                    moves.append({"move_id": f"move_vehicle_{vehicle.get('id')}", "type": "move_vehicle", "player_id": player_id,
                                 "vehicle_id": vehicle.get("id"), "from_position": vehicle.get("position"), "to_position": vehicle.get("position")})
            moves.append({"move_id": "fire", "type": "fire", "player_id": player_id})
            moves.append({"move_id": "rally", "type": "rally", "player_id": player_id})
            moves.append({"move_id": "concentrate_fire", "type": "concentrate_fire", "player_id": player_id})
            moves.append({"move_id": "grenade_attack", "type": "grenade_attack", "player_id": player_id})
            moves.append({"move_id": "at_fire", "type": "at_fire", "player_id": player_id})
            moves.append({"move_id": "place_vof", "type": "place_vof", "player_id": player_id, "position": 0, "rating": "A"})
            moves.append({"move_id": "place_pdf", "type": "place_pdf", "player_id": player_id, "position": 0, "direction": "N"})
            moves.append({"move_id": "place_smoke", "type": "place_smoke", "player_id": player_id, "position": 0})
            moves.append({"move_id": "call_fire_mission", "type": "call_fire_mission", "player_id": player_id, "mission_type": "HE"})
            moves.append({"move_id": "call_fire_mission_smoke", "type": "call_fire_mission", "player_id": player_id, "mission_type": "smoke_wp"})
            moves.append({"move_id": "demolition", "type": "demolition_charge", "player_id": player_id})
            moves.append({"move_id": "place_mine", "type": "place_mine", "player_id": player_id, "position": 0})
            moves.append({"move_id": "enemy_activity_check", "type": "enemy_activity_check", "player_id": player_id})
            moves.append({"move_id": "place_illumination", "type": "place_illumination", "player_id": player_id, "position": 0})
            moves.append({"move_id": "embark", "type": "embark", "player_id": player_id})
            moves.append({"move_id": "disembark", "type": "disembark", "player_id": player_id})
            moves.append({"move_id": "load_helicopter", "type": "load_helicopter", "player_id": player_id})
            moves.append({"move_id": "land_helicopter", "type": "land_helicopter", "player_id": player_id, "position": 0})
            moves.append({"move_id": "amphibious_assault", "type": "amphibious_assault", "player_id": player_id})
            moves.append({"move_id": "gain_experience", "type": "gain_experience", "player_id": player_id, "amount": 1})
            moves.append({"move_id": "spend_experience", "type": "spend_experience", "player_id": player_id, "skill": "leadership"})
            moves.append({"move_id": "request_replacements", "type": "request_replacements", "player_id": player_id})
            moves.append({"move_id": "end_mission", "type": "end_mission", "player_id": player_id})
            moves.append({"move_id": "enter_building", "type": "enter_building", "player_id": player_id, "position": 0})
            moves.append({"move_id": "breach_building", "type": "breach_building", "player_id": player_id, "position": 0})
            moves.append({"move_id": "barricade", "type": "barricade", "player_id": player_id, "position": 0})
            moves.append({"move_id": "urban_combat", "type": "urban_combat", "player_id": player_id})
            return moves
        return []



















    def _next_phase(self, phase: str) -> str:
        idx = PHASES.index(phase)
        return PHASES[idx + 1] if idx + 1 < len(PHASES) else "game_over"

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_move(state, move):
            raise IllegalMoveError("illegal move")
        new = {**state, "game_data": {**state.get("game_data", {})}}
        gd = new["game_data"]
        if move.get("type") == "start_mission":
            gd["phase"] = "friendly_higher_hq_event"
        elif move.get("type") == "lay_out_map":
            cards = move.get("cards", [])
            gd.setdefault("map", {})["cards"] = cards
        elif move.get("type") == "place_vehicle":
            gd.setdefault("company", {}).setdefault("vehicles", []).append({"id": move["vehicle_id"], "position": move["position"]})
        elif move.get("type") == "helicopter_assault":
            gd.setdefault("markers", []).append({"type": "helicopter_assault"})
        elif move.get("type") == "resolve_pc":
            gd.setdefault("pc_markers", []).append({"id": move["pc_id"], "resolved": True})
            gd["contact_level"] = move.get("contact_level", "contact")
            # Place enemy package
            gd.setdefault("enemy_packages", []).append({"id": f"pkg_{move['pc_id']}", "position": move.get("position", 0), "type": move.get("enemy_type", "infantry"), "strength": move.get("strength", "squad")})
            gd.setdefault("enemy", []).append({"id": f"enemy_{move['pc_id']}", "position": move.get("position", 0), "type": move.get("enemy_type", "infantry")})
        elif move.get("type") == "enemy_activity_check":
            gd["contact_level"] = gd.get("contact_level", "no_contact")
            # Simple enemy activity
            if gd.get("contact_level") in ["contact", "engaged", "heavily_engaged"]:
                gd.setdefault("markers", []).append({"type": "enemy_activity", "resolved": False})
            gd.setdefault("enemy_packages", [])
            ammo = gd.setdefault("company", {}).setdefault("ammo", {})
            mission = move.get("mission_type", "HE")
            if mission in ["HE", "battalion", "FPF", "TOT", "air_strike"]:
                ammo["mtr"] = max(0, ammo.get("mtr", 0) - 1)
            elif mission in ["smoke_wp"]:
                ammo["mtr"] = max(0, ammo.get("mtr", 0) - 1)
            elif mission == "illumination":
                ammo["mtr"] = max(0, ammo.get("mtr", 0) - 1)
            gd.setdefault("markers", []).append({"type": "fire_mission", "mission_type": mission, "resolved": False})
        elif move.get("type") == "demolition_charge":
            ammo = gd.setdefault("company", {}).setdefault("ammo", {})
            ammo["demo"] = max(0, ammo.get("demo", 0) - 1)
            gd.setdefault("markers", []).append({"type": "demolition", "resolved": False})
        elif move.get("type") == "place_mine":
            gd.setdefault("markers", []).append({"type": "mine", "position": move["position"], "resolved": False})
        elif move.get("type") == "flamethrower_attack":
            ammo = gd.setdefault("company", {}).setdefault("ammo", {})
            ammo["f"] = max(0, ammo.get("f", 0) - 1)
            gd.setdefault("markers", []).append({"type": "flamethrower", "resolved": False})
        elif move.get("type") == "sniper":
            gd.setdefault("markers", []).append({"type": "sniper", "resolved": False})
        elif move.get("type") == "register_target":
            gd.setdefault("registered_targets", []).append(move["position"])
            gd.setdefault("markers", []).append({"type": "grenade", "resolved": False})
        elif move.get("type") == "concentrate_fire":
            gd.setdefault("markers", []).append({"type": "concentrate_fire", "resolved": False, "positions": move.get("positions", [])})
        elif move.get("type") == "activate_hq":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            activated = cmd.setdefault("activated", [])
            hq_id = move["hq_id"]
            if hq_id not in activated:
                activated.append(hq_id)
        elif move.get("type") == "draw_commands":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            activated = cmd.get("activated", [])
            total = max(1, len(activated) * 2)
            cmd["commands_pool"] = cmd.get("commands_pool", 0) + total
            cmd["command_draw"] = cmd.get("command_draw", []) + [total]
        elif move.get("type") == "exhort":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "exhort", "resolved": False})
        elif move.get("type") == "reconstitute":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "reconstitute", "resolved": False})
                # Track reconstitution
                gd.setdefault("reconstituted_units", []).append({"cost": 1, "resolved": False})
        elif move.get("type") == "create_runner":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("company", {}).setdefault("runners", []).append({"id": move.get("runner_id", "runner_1")})
        elif move.get("type") == "dispatch_runner":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "runner_dispatched", "target": move.get("target")})
        elif move.get("type") == "deploy_pyrotechnic":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "pyrotechnic", "signal": move.get("signal")})
        elif move.get("type") == "designate_tactical_control":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "tactical_control", "position": move.get("position")})
        elif move.get("type") == "move_action":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "move_action", "resolved": False})
        elif move.get("type") == "open_fire":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            if pool > 0:
                cmd["commands_pool"] = pool - 1
                gd.setdefault("markers", []).append({"type": "fire", "resolved": False})
            gd.setdefault("vof_markers", []).append({"position": move["position"], "rating": move["rating"]})
        elif move.get("type") == "place_pdf":
            gd.setdefault("pdf_markers", []).append({"position": move["position"], "direction": move["direction"]})
        elif move.get("type") == "place_smoke":
            gd.setdefault("smoke_markers", []).append({"type": "smoke", "position": move["position"], "duration": move.get("duration", 2)})
        elif move.get("type") == "fire":
            gd.setdefault("markers", []).append({"type": "fire", "resolved": False})
        elif move.get("type") == "rally":
            gd.setdefault("markers", []).append({"type": "rally", "resolved": False})
            # Rally all pinned units
            company = gd.setdefault("company", {})
            units = company.setdefault("units", [])
            for u in units:
                if u.get("status") == "pinned":
                    u["status"] = "good_order"
                    u["exposed"] = False
        elif move.get("type") == "move_unit":
            company = gd.setdefault("company", {})
            units = company.setdefault("units", [])
            unit_id = move["unit_id"]
            from_pos = move.get("from_position", 0)
            to_pos = move["to_position"]
            for u in units:
                if u.get("id") == unit_id:
                    u["position"] = to_pos
                    u["exposed"] = move.get("exposed", False)
                    # Track movement cost (1 command per card crossed)
                    if from_pos != to_pos:
                        map_data = gd.get("map", {})
                        cols = map_data.get("cols", 4)
                        if cols:
                            from_r, from_c = divmod(from_pos, cols)
                            to_r, to_c = divmod(to_pos, cols)
                            distance = abs(from_r - to_r) + abs(from_c - to_c)
                            if distance > 0:
                                cmd = company.setdefault("command", {})
                                cost = distance
                                pool = cmd.get("commands_pool", 0)
                                cmd["commands_pool"] = max(0, pool - cost)
                    break
        elif move.get("type") == "place_unit":
            company = gd.setdefault("company", {})
            units = company.setdefault("units", [])
            unit_id = move["unit_id"]
            for u in units:
                if u.get("id") == unit_id:
                    u["position"] = move["position"]
                    u["status"] = u.get("status", "good_order")
                    break
            else:
                # Don't add new units, just place existing ones
                units.append({
                    "id": unit_id,
                    "position": move["position"],
                    "status": "good_order",
                    "experience_level": move.get("experience_level", "Line"),
                    "step_count": move.get("step_count", 1),
                    "ammo": move.get("ammo", "full"),
                    "vof_rating": move.get("vof_rating", "A")
                })
        elif move.get("type") == "place_enemy":
            gd.setdefault("enemy", []).append({
                "id": move["enemy_id"],
                "position": move["position"],
                "type": move.get("enemy_type", "infantry")
            })
        elif move.get("type") == "place_marker":
            gd.setdefault("markers", []).append({"type": move["marker"], "position": move["position"]})
        elif move.get("type") == "advance_phase":
            gd["phase"] = move["next_phase"]
        elif move.get("type") == "amphibious_assault":
            gd.setdefault("markers", []).append({"type": "amphibious_assault", "resolved": False})
        elif move.get("type") == "at_fire":
            gd.setdefault("markers", []).append({"type": "at_fire", "resolved": False})
        elif move.get("type") == "barricade":
            gd.setdefault("markers", []).append({"type": "barricade", "position": move.get("position"), "resolved": False})
        elif move.get("type") == "breach_building":
            gd.setdefault("markers", []).append({"type": "breach", "position": move.get("position"), "resolved": False})
        elif move.get("type") == "call_fire_mission":
            gd.setdefault("markers", []).append({"type": "fire_mission", "mission_type": move.get("mission_type", "HE"), "resolved": False})
        elif move.get("type") == "disembark":
            gd.setdefault("markers", []).append({"type": "disembark", "resolved": False})
        elif move.get("type") == "embark":
            gd.setdefault("markers", []).append({"type": "embark", "resolved": False})
        elif move.get("type") == "end_mission":
            gd["phase"] = "game_over"
        elif move.get("type") == "enter_building":
            gd.setdefault("markers", []).append({"type": "enter_building", "position": move.get("position"), "resolved": False})
        elif move.get("type") == "gain_experience":
            company = gd.setdefault("company", {})
            company["experience"] = company.get("experience", 0) + move.get("amount", 1)
        elif move.get("type") == "land_helicopter":
            gd.setdefault("markers", []).append({"type": "helicopter_landing", "position": move.get("position"), "resolved": False})
        elif move.get("type") == "load_helicopter":
            gd.setdefault("markers", []).append({"type": "helicopter_load", "resolved": False})
        elif move.get("type") == "move_vehicle":
            company = gd.setdefault("company", {})
            vehicles = company.setdefault("vehicles", [])
            vehicle_id = move["vehicle_id"]
            for v in vehicles:
                if v.get("id") == vehicle_id:
                    v["position"] = move["to_position"]
                    break
        elif move.get("type") == "place_illumination":
            gd.setdefault("markers", []).append({"type": "illumination", "position": move.get("position"), "resolved": False})
        elif move.get("type") == "place_vof":
            gd.setdefault("vof_markers", []).append({"type": "vof", "position": move.get("position"), "rating": move.get("rating", "A"), "resolved": False})
        elif move.get("type") == "plan_assault":
            gd.setdefault("markers", []).append({"type": "assault_plan", "resolved": False})
        elif move.get("type") == "request_replacements":
            gd.setdefault("markers", []).append({"type": "replacement_request", "resolved": False})
        elif move.get("type") == "set_visibility":
            vis = gd.setdefault("visibility", {})
            vis["limited"] = move.get("limited", False)
        elif move.get("type") == "spend_command":
            cmd = gd.setdefault("company", {}).setdefault("command", {})
            pool = cmd.get("commands_pool", 0)
            amount = move.get("amount", 1)
            if pool >= amount:
                cmd["commands_pool"] = pool - amount
        elif move.get("type") == "spend_experience":
            company = gd.setdefault("company", {})
            company.setdefault("skills", []).append(move.get("skill", "leadership"))
        elif move.get("type") == "urban_combat":
            gd.setdefault("markers", []).append({"type": "urban_combat", "resolved": False})
        return new








    def calculate_movement_cost(self, from_pos, to_pos, game_data=None):
        gd = game_data or {}
        map_data = gd.get("map", {})
        cols = map_data.get("cols", 4)
        if cols and from_pos != to_pos:
            from_r, from_c = divmod(from_pos, cols)
            to_r, to_c = divmod(to_pos, cols)
            return abs(from_r - to_r) + abs(from_c - to_c)
        return 0

    def is_within_card_movement(self, from_pos, to_pos):
        return from_pos == to_pos

    def get_terrain_trafficability(self, card_id):
        from app.games.fields_of_fire.terrain import terrain_card, get_card
        card_data = get_card(card_id)
        if card_data:
            tc = terrain_card(card_data.get("terrain_type", "open_field"), card_id)
            return tc.get("trafficability", "good")
        return "good"

    def place_smoke_marker(self, position, duration=2, game_data=None):
        gd = game_data or {}
        smoke = {"type": "smoke", "position": position, "duration": duration, "resolved": False}
        gd.setdefault("smoke_markers", []).append(smoke)
        return smoke

    def dissipate_smoke(self, game_data=None):
        gd = game_data or {}
        smoke_markers = gd.get("smoke_markers", [])
        remaining = []
        for m in smoke_markers:
            if isinstance(m, dict) and m.get("type") == "smoke":
                dur = m.get("duration", 1)
                if dur > 1:
                    m["duration"] = dur - 1
                    remaining.append(m)
                # else: smoke dissipates
            else:
                remaining.append(m)
        gd["smoke_markers"] = remaining
        return len(smoke_markers) - len(remaining)

    def is_smoke_at(self, position, game_data=None):
        gd = game_data or {}
        smoke_markers = gd.get("smoke_markers", [])
        for m in smoke_markers:
            if isinstance(m, dict) and m.get("position") == position:
                return True
        return False

    def smoke_blocks_los(self, position, game_data=None):
        return self.is_smoke_at(position, game_data)

    def smoke_movement_penalty(self, position, game_data=None):
        if self.is_smoke_at(position, game_data):
            return 1  # +1 movement cost in smoke
        return 0

    def smoke_combat_modifier(self, position, game_data=None):
        if self.is_smoke_at(position, game_data):
            return -1  # -1 to hit in smoke
        return 0

    def place_vof_marker(self, position, rating, game_data=None):
        gd = game_data or {}
        vof = {"type": "vof", "position": position, "rating": rating, "resolved": False}
        gd.setdefault("vof_markers", []).append(vof)
        return vof

    def get_vof_at(self, position, game_data=None):
        gd = game_data or {}
        vof_markers = gd.get("vof_markers", [])
        for m in vof_markers:
            if isinstance(m, dict) and m.get("position") == position:
                return m
        return None

    def resolve_vof(self, position, game_data=None):
        gd = game_data or {}
        vof = self.get_vof_at(position, gd)
        if not vof:
            return None
        vof["resolved"] = True
        # VOF rating determines hit probability
        rating = vof.get("rating", "C")
        hit_mod = {"A": 3, "B": 2, "C": 1, "D": 0}.get(rating, 1)
        return {"position": position, "rating": rating, "hit_modifier": hit_mod, "resolved": True}

    def vof_effect_on_unit(self, unit, vof_rating):
        # Returns status effect based on VOF rating
        effects = {
            "A": "hit",
            "B": "pin",
            "C": "no_effect",
            "D": "no_effect",
        }
        return effects.get(vof_rating, "no_effect")

    def clear_vof_markers(self, position=None, game_data=None):
        gd = game_data or {}
        vof_markers = gd.get("vof_markers", [])
        if position is None:
            gd["vof_markers"] = []
            return len(vof_markers)
        remaining = [m for m in vof_markers if not (isinstance(m, dict) and m.get("position") == position)]
        removed = len(vof_markers) - len(remaining)
        gd["vof_markers"] = remaining
        return removed

    def resolve_fire(self, attacker_pos, target_pos, vof_rating="C", pdf_rating="none", game_data=None):
        gd = game_data or {}
        # Base hit modifier from VOF rating
        vof_mod = {"A": 3, "B": 2, "C": 1, "D": 0}.get(vof_rating, 1)
        # Cover modifier for target
        cover = self.get_cover(target_pos if isinstance(target_pos, str) else None)
        cover_mod = self.get_cover_modifier(cover.get("high", 0)) if isinstance(cover, dict) else 0
        # Smoke modifier
        smoke_mod = self.smoke_combat_modifier(target_pos if isinstance(target_pos, int) else None, gd)
        # Total modifier
        total_mod = vof_mod + cover_mod + smoke_mod
        # Determine result
        if total_mod >= 3:
            result = "HIT"
        elif total_mod >= 1:
            result = "PIN"
        else:
            result = "MISS"
        return {"result": result, "modifier": total_mod, "vof": vof_rating, "cover": cover_mod, "smoke": smoke_mod}

    def apply_hit_effect(self, unit, hit_type, game_data=None):
        gd = game_data or {}
        if hit_type == "HIT":
            unit["status"] = "casualty"
            gd.setdefault("company", {}).setdefault("casualties", []).append(unit)
        elif hit_type == "PIN":
            unit["status"] = "pinned"
            unit["exposed"] = True
        return unit

    def rally_unit(self, unit, game_data=None):
        gd = game_data or {}
        if unit.get("status") == "pinned":
            unit["status"] = "good_order"
            unit["exposed"] = False
            return True
        return False

    def get_combat_modifiers(self, attacker_pos, target_pos, game_data=None):
        gd = game_data or {}
        modifiers = {}
        # Elevation modifier
        elev_a = 0
        elev_b = 0
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if isinstance(attacker_pos, int) and attacker_pos < len(cards):
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data = get_card(cards[attacker_pos])
            if card_data:
                tc = terrain_card(card_data.get("terrain_type", "open_field"), cards[attacker_pos])
                elev_a = tc.get("elevation", 0)
        if isinstance(target_pos, int) and target_pos < len(cards):
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data = get_card(cards[target_pos])
            if card_data:
                tc = terrain_card(card_data.get("terrain_type", "open_field"), cards[target_pos])
                elev_b = tc.get("elevation", 0)
        if elev_a > elev_b:
            modifiers["elevation"] = 1
        elif elev_a < elev_b:
            modifiers["elevation"] = -1
        else:
            modifiers["elevation"] = 0
        # Cover modifier
        if isinstance(target_pos, int) and target_pos < len(cards):
            card_id = cards[target_pos]
            cover = self.get_cover(card_id)
            modifiers["cover"] = self.get_cover_modifier(cover.get("high", 0))
        else:
            modifiers["cover"] = 0
        # Concealment bonus
        target_unit = None
        for u in gd.get("company", {}).get("units", []):
            if u.get("position") == target_pos:
                target_unit = u
                break
        if target_unit:
            modifiers["concealment"] = self.get_concealment_bonus(target_unit, gd)
        else:
            modifiers["concealment"] = 0
        return modifiers

    def reconstitute_unit(self, casualty_id, new_unit_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        casualties = company.get("casualties", [])
        # Find the casualty
        casualty = None
        for c in casualties:
            if isinstance(c, dict) and c.get("id") == casualty_id:
                casualty = c
                break
            elif c == casualty_id:
                casualty = {"id": casualty_id}
                break
        if not casualty:
            return False
        # Remove from casualties
        company["casualties"] = [c for c in casualties if not (isinstance(c, dict) and c.get("id") == casualty_id) and c != casualty_id]
        # Create new unit
        new_unit = {
            "id": new_unit_id,
            "type": casualty.get("type", "squad") if isinstance(casualty, dict) else "squad",
            "position": None,
            "status": "good_order",
            "reconstituted": True,
            "original_id": casualty_id,
        }
        company.setdefault("units", []).append(new_unit)
        # Track reconstituted units
        gd.setdefault("reconstituted_units", []).append({"original": casualty_id, "new": new_unit_id})
        return True

    def get_reconstituted_units(self, game_data=None):
        gd = game_data or {}
        return gd.get("reconstituted_units", [])

    def rally_all_pinned(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        rallied = 0
        for u in units:
            if u.get("status") == "pinned":
                u["status"] = "good_order"
                u["exposed"] = False
                rallied += 1
        return rallied

    def get_pinned_units(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        return [u for u in units if u.get("status") == "pinned"]

    def get_casualty_count(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        return len(company.get("casualties", []))

    WEAPON_STATS = {
        "rifle": {"range": 4, "vof_rating": "C", "ammo_type": "none", "burst": 0},
        "mg": {"range": 6, "vof_rating": "B", "ammo_type": "mg", "burst": 2},
        "lmg": {"range": 4, "vof_rating": "B", "ammo_type": "mg", "burst": 1},
        "mortar": {"range": 10, "vof_rating": "A", "ammo_type": "mtr", "burst": 0},
        "rcl": {"range": 8, "vof_rating": "B", "ammo_type": "rcl", "burst": 0},
        "rocket": {"range": 6, "vof_rating": "B", "ammo_type": "rkt", "burst": 0},
        "pistol": {"range": 1, "vof_rating": "D", "ammo_type": "none", "burst": 0},
        "smg": {"range": 2, "vof_rating": "C", "ammo_type": "none", "burst": 1},
    }

    def get_weapon_stats(self, weapon_type):
        return self.WEAPON_STATS.get(weapon_type, {"range": 2, "vof_rating": "C", "ammo_type": "none", "burst": 0})

    def calculate_vof_rating(self, weapon_type, num_weapons=1, concentrated=False):
        stats = self.get_weapon_stats(weapon_type)
        base_rating = stats.get("vof_rating", "C")
        # Concentrated fire upgrades rating
        if concentrated and num_weapons >= 2:
            ratings = ["D", "C", "B", "A"]
            idx = ratings.index(base_rating) if base_rating in ratings else 2
            if idx < len(ratings) - 1:
                base_rating = ratings[idx + 1]
        # Multiple weapons can upgrade rating
        if num_weapons >= 3 and base_rating in ("C", "B"):
            ratings = ["D", "C", "B", "A"]
            idx = ratings.index(base_rating)
            if idx < len(ratings) - 1:
                base_rating = ratings[idx + 1]
        return base_rating

    def get_weapon_range(self, weapon_type):
        stats = self.get_weapon_stats(weapon_type)
        return stats.get("range", 2)

    def get_weapon_ammo_type(self, weapon_type):
        stats = self.get_weapon_stats(weapon_type)
        return stats.get("ammo_type", "none")

    def get_weapon_burst(self, weapon_type):
        stats = self.get_weapon_stats(weapon_type)
        return stats.get("burst", 0)

    def consume_ammo(self, weapon_type, amount=1, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        ammo = company.setdefault("ammo", {})
        ammo_type = self.get_weapon_ammo_type(weapon_type)
        if ammo_type == "none":
            return True
        current = ammo.get(ammo_type, 0)
        if current < amount:
            return False
        ammo[ammo_type] = current - amount
        return True

    def get_ammo_count(self, ammo_type, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        ammo = company.get("ammo", {})
        return ammo.get(ammo_type, 0)

    def list_weapons(self):
        return list(self.WEAPON_STATS.keys())

    def resolve_grenade_attack(self, position, grenade_type="frag", game_data=None):
        gd = game_data or {}
        # Grenade attack resolution
        result = {"position": position, "type": grenade_type, "resolved": False}
        # Base hit chance for grenade
        hit_chance = 0.6 if grenade_type == "frag" else 0.4
        # Check if target is in cover
        cover = self.get_cover(position if isinstance(position, str) else None)
        if isinstance(cover, dict) and cover.get("high", 0) >= 2:
            hit_chance -= 0.2
        result["hit_chance"] = hit_chance
        result["resolved"] = True
        # Consume grenade ammo
        company = gd.get("company", {})
        ammo = company.setdefault("ammo", {})
        if ammo.get("demo", 0) > 0:
            ammo["demo"] = max(0, ammo.get("demo", 0) - 1)
        gd.setdefault("markers", []).append({"type": "grenade", "position": position, "resolved": True})
        return result

    def resolve_concentrated_fire(self, positions, weapon_type="rifle", game_data=None):
        gd = game_data or {}
        # Multiple units combine fire on a target
        num_units = len(positions) if isinstance(positions, list) else 1
        # Concentrated fire upgrades VOF rating
        vof_rating = self.calculate_vof_rating(weapon_type, num_units, concentrated=True)
        result = {
            "positions": positions,
            "weapon_type": weapon_type,
            "num_units": num_units,
            "vof_rating": vof_rating,
            "concentrated": True,
        }
        gd.setdefault("markers", []).append({"type": "concentrate_fire", "positions": positions, "vof_rating": vof_rating, "resolved": False})
        return result

    def grenade_attack_effect(self, target_status, grenade_type="frag"):
        # Returns effect on target
        if grenade_type == "frag":
            if target_status in ("good_order", "pinned"):
                return "hit"
        elif grenade_type == "smoke":
            return "smoke_placed"
        elif grenade_type == "illumination":
            return "illuminated"
        return "no_effect"

    def get_grenade_types(self):
        return ["frag", "smoke", "illumination", "concussion"]

    VEHICLE_STATS = {
        "m113": {"name": "M113 APC", "armor": 2, "weapon": "mg", "movement": 6, "capacity": 12, "type": "apc"},
        "m48": {"name": "M48 Patton", "armor": 4, "weapon": "90mm", "movement": 4, "capacity": 0, "type": "tank"},
        "m551": {"name": "M551 Sheridan", "armor": 3, "weapon": "152mm", "movement": 5, "capacity": 0, "type": "tank"},
        "m151": {"name": "M151 Jeep", "armor": 0, "weapon": "none", "movement": 8, "capacity": 4, "type": "jeep"},
        "truck": {"name": "Truck", "armor": 0, "weapon": "none", "movement": 8, "capacity": 12, "type": "truck"},
    }

    def get_vehicle_stats(self, vehicle_type):
        return self.VEHICLE_STATS.get(vehicle_type, {"name": vehicle_type, "armor": 0, "weapon": "none", "movement": 4, "capacity": 0, "type": "unknown"})

    def vehicle_can_move_to(self, vehicle_type, terrain_trafficability):
        stats = self.get_vehicle_stats(vehicle_type)
        vtype = stats.get("type", "unknown")
        if vtype == "tank":
            return terrain_trafficability in ("good", "fair", "poor")
        elif vtype in ("apc", "truck", "jeep"):
            return terrain_trafficability in ("good", "fair")
        return False

    def resolve_vof_vs_vehicle(self, vof_rating, vehicle_type):
        stats = self.get_vehicle_stats(vehicle_type)
        armor = stats.get("armor", 0)
        vof_mod = {"A": 3, "B": 2, "C": 1, "D": 0}.get(vof_rating, 1)
        # Armor reduces hit chance
        effective = vof_mod - armor
        if effective >= 3:
            return "destroyed"
        elif effective >= 2:
            return "immobilized"
        elif effective >= 1:
            return "suppressed"
        return "no_effect"

    def embark_unit(self, unit_id, vehicle_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        vehicles = company.get("vehicles", [])
        unit = None
        vehicle = None
        for u in units:
            if u.get("id") == unit_id:
                unit = u
                break
        for v in vehicles:
            if v.get("id") == vehicle_id:
                vehicle = v
                break
        if not unit or not vehicle:
            return False
        stats = self.get_vehicle_stats(vehicle.get("type", "unknown"))
        capacity = stats.get("capacity", 0)
        embarked = vehicle.setdefault("embarked", [])
        if len(embarked) >= capacity:
            return False
        embarked.append(unit_id)
        unit["position"] = vehicle.get("position")
        unit["embarked_in"] = vehicle_id
        return True

    def disembark_unit(self, unit_id, position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        vehicles = company.get("vehicles", [])
        for u in units:
            if u.get("id") == unit_id:
                vehicle_id = u.get("embarked_in")
                if vehicle_id:
                    for v in vehicles:
                        if v.get("id") == vehicle_id:
                            embarked = v.get("embarked", [])
                            if unit_id in embarked:
                                embarked.remove(unit_id)
                            break
                u["position"] = position
                u["embarked_in"] = None
                return True
        return False

    def get_vehicle_at(self, position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        vehicles = company.get("vehicles", [])
        for v in vehicles:
            if v.get("position") == position:
                return v
        return None

    def list_vehicle_types(self):
        return list(self.VEHICLE_STATS.keys())

    def place_mine_marker(self, position, mine_type="ap", game_data=None):
        gd = game_data or {}
        mine = {"type": "mine", "mine_type": mine_type, "position": position, "detonated": False, "discovered": False}
        gd.setdefault("markers", []).append(mine)
        return mine

    def detonate_mine(self, position, game_data=None):
        gd = game_data or {}
        markers = gd.get("markers", [])
        for m in markers:
            if isinstance(m, dict) and m.get("type") == "mine" and m.get("position") == position and not m.get("detonated"):
                m["detonated"] = True
                # Mine effect: hit to units on card
                units_on_card = [u for u in gd.get("company", {}).get("units", []) if u.get("position") == position]
                for u in units_on_card:
                    u["status"] = "casualty"
                gd.setdefault("company", {}).setdefault("casualties", []).extend(units_on_card)
                return {"position": position, "detonated": True, "casualties": len(units_on_card)}
        return {"position": position, "detonated": False}

    def place_claymore(self, position, direction, game_data=None):
        gd = game_data or {}
        claymore = {"type": "claymore", "position": position, "direction": direction, "detonated": False}
        gd.setdefault("markers", []).append(claymore)
        return claymore

    def detonate_claymore(self, position, direction, game_data=None):
        gd = game_data or {}
        markers = gd.get("markers", [])
        for m in markers:
            if isinstance(m, dict) and m.get("type") == "claymore" and m.get("position") == position and not m.get("detonated"):
                m["detonated"] = True
                # Claymore affects cards in a direction
                return {"position": position, "direction": direction, "detonated": True, "arc": "60 degrees"}
        return {"position": position, "detonated": False}

    def resolve_flamethrower(self, position, game_data=None):
        gd = game_data or {}
        # Flamethrower: automatic hit on all targets on card
        units_on_card = [u for u in gd.get("company", {}).get("units", []) if u.get("position") == position]
        enemy_on_card = [e for e in gd.get("enemy", []) if e.get("position") == position]
        # Consume fuel
        ammo = gd.setdefault("company", {}).setdefault("ammo", {})
        ammo["f"] = max(0, ammo.get("f", 0) - 1)
        gd.setdefault("markers", []).append({"type": "flamethrower", "position": position, "resolved": True})
        return {"position": position, "units_affected": len(units_on_card) + len(enemy_on_card), "resolved": True}

    def resolve_sniper(self, position, target_id, game_data=None):
        gd = game_data or {}
        # Sniper: single precise shot
        result = {"position": position, "target": target_id, "resolved": False}
        # Sniper ignores cover partially
        result["cover_ignored"] = True
        result["resolved"] = True
        gd.setdefault("markers", []).append({"type": "sniper", "position": position, "target": target_id, "resolved": True})
        return result

    def resolve_demolition(self, position, structure_type="building", game_data=None):
        gd = game_data or {}
        ammo = gd.setdefault("company", {}).setdefault("ammo", {})
        ammo["demo"] = max(0, ammo.get("demo", 0) - 1)
        result = {"position": position, "structure": structure_type, "destroyed": True}
        gd.setdefault("markers", []).append({"type": "demolition", "position": position, "structure": structure_type, "resolved": True})
        return result

    def get_mine_types(self):
        return ["ap", "at", "booby_trap"]

    def is_mine_at(self, position, game_data=None):
        gd = game_data or {}
        markers = gd.get("markers", [])
        for m in markers:
            if isinstance(m, dict) and m.get("type") == "mine" and m.get("position") == position and not m.get("detonated"):
                return True
        return False

    def register_target(self, position, game_data=None):
        gd = game_data or {}
        targets = gd.setdefault("registered_targets", [])
        if position not in targets:
            targets.append(position)
        return position

    def is_target_registered(self, position, game_data=None):
        gd = game_data or {}
        targets = gd.get("registered_targets", [])
        return position in targets

    def resolve_fire_mission(self, mission_type, target_position, game_data=None):
        gd = game_data or {}
        # Check prerequisites
        if not self.is_target_registered(target_position, gd):
            return {"resolved": False, "reason": "target not registered"}
        # Consume ammo
        ammo = gd.setdefault("company", {}).setdefault("ammo", {})
        if mission_type in ("HE", "battalion", "FPF", "TOT", "air_strike"):
            if ammo.get("mtr", 0) <= 0:
                return {"resolved": False, "reason": "no mortar ammo"}
            ammo["mtr"] = max(0, ammo.get("mtr", 0) - 1)
        elif mission_type in ("smoke_wp",):
            if ammo.get("mtr", 0) <= 0:
                return {"resolved": False, "reason": "no mortar ammo"}
            ammo["mtr"] = max(0, ammo.get("mtr", 0) - 1)
        elif mission_type == "illumination":
            if ammo.get("mtr", 0) <= 0:
                return {"resolved": False, "reason": "no mortar ammo"}
            ammo["mtr"] = max(0, ammo.get("mtr", 0) - 1)

        # Resolve effects
        result = {"mission_type": mission_type, "target": target_position, "resolved": True}
        if mission_type in ("HE", "battalion", "FPF", "TOT", "air_strike"):
            result["effect"] = "high_explosive"
            result["casualties"] = 0  # Would be calculated based on units on card
        elif mission_type == "smoke_wp":
            result["effect"] = "smoke"
            self.place_smoke_marker(target_position, duration=2, game_data=gd)
        elif mission_type == "illumination":
            result["effect"] = "illumination"
            vis = gd.setdefault("visibility", {})
            vis["illumination"] = target_position

        gd.setdefault("markers", []).append({"type": "fire_mission", "mission_type": mission_type, "target": target_position, "resolved": True})
        return result

    def get_fire_mission_types(self):
        return ["HE", "smoke_wp", "illumination", "battalion", "FPF", "TOT", "air_strike"]

    def get_fire_mission_prerequisites(self, mission_type):
        prereqs = {"target_registered": True}
        if mission_type in ("HE", "battalion", "FPF", "TOT"):
            prereqs["observer"] = True
        if mission_type == "air_strike":
            prereqs["air_observer"] = True
        return prereqs

    CONTACT_LEVELS = ["no_contact", "contact", "engaged", "heavily_engaged"]

    def place_pc_marker(self, position, pc_id="pc_1", game_data=None):
        gd = game_data or {}
        pc = {"id": pc_id, "type": "pc", "position": position, "resolved": False, "contact_level": "no_contact"}
        gd.setdefault("pc_markers", []).append(pc)
        return pc

    def get_pc_at(self, position, game_data=None):
        gd = game_data or {}
        pc_markers = gd.get("pc_markers", [])
        for pc in pc_markers:
            if isinstance(pc, dict) and pc.get("position") == position:
                return pc
        return None

    def resolve_pc_contact(self, pc_id, contact_level="contact", enemy_type="infantry", strength="squad", game_data=None):
        gd = game_data or {}
        pc_markers = gd.get("pc_markers", [])
        for pc in pc_markers:
            if isinstance(pc, dict) and pc.get("id") == pc_id:
                pc["resolved"] = True
                pc["contact_level"] = contact_level
                gd["contact_level"] = contact_level
                # Generate enemy package
                enemy_pkg = {"id": "pkg_" + pc_id, "position": pc.get("position", 0), "type": enemy_type, "strength": strength}
                gd.setdefault("enemy_packages", []).append(enemy_pkg)
                # Generate enemy unit
                enemy_unit = {"id": "enemy_" + pc_id, "position": pc.get("position", 0), "type": enemy_type, "strength": strength}
                gd.setdefault("enemy", []).append(enemy_unit)
                return {"pc_id": pc_id, "contact_level": contact_level, "enemy_package": enemy_pkg, "resolved": True}
        return {"pc_id": pc_id, "resolved": False}

    def get_contact_level(self, game_data=None):
        gd = game_data or {}
        return gd.get("contact_level", "no_contact")

    def set_contact_level(self, level, game_data=None):
        gd = game_data or {}
        if level in self.CONTACT_LEVELS:
            gd["contact_level"] = level
            return True
        return False

    def get_enemy_packages(self, game_data=None):
        gd = game_data or {}
        return gd.get("enemy_packages", [])

    def get_enemies(self, game_data=None):
        gd = game_data or {}
        return gd.get("enemy", [])

    def place_enemy_unit(self, enemy_id, position, enemy_type="infantry", game_data=None):
        gd = game_data or {}
        enemy = {"id": enemy_id, "position": position, "type": enemy_type}
        gd.setdefault("enemy", []).append(enemy)
        return enemy

    def get_enemies_at(self, position, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        return [e for e in enemies if isinstance(e, dict) and e.get("position") == position]

    def enemy_activity_check(self, game_data=None):
        gd = game_data or {}
        contact = gd.get("contact_level", "no_contact")
        enemies = gd.get("enemy", [])
        result = {"contact_level": contact, "enemies_checked": len(enemies), "actions": []}
        if contact in ("contact", "engaged", "heavily_engaged"):
            # Enemy may move or fire
            result["actions"].append("enemy_move")
            result["actions"].append("enemy_fire")
            gd.setdefault("markers", []).append({"type": "enemy_activity", "resolved": False})
        return result

    def enemy_move(self, enemy_id, from_pos, to_pos, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        for e in enemies:
            if isinstance(e, dict) and e.get("id") == enemy_id:
                e["position"] = to_pos
                return True
        return False

    def enemy_fire(self, enemy_id, target_pos, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        for e in enemies:
            if isinstance(e, dict) and e.get("id") == enemy_id:
                # Enemy fires at target position
                gd.setdefault("markers", []).append({"type": "enemy_fire", "enemy_id": enemy_id, "target": target_pos, "resolved": False})
                return True
        return False

    def enemy_fall_back(self, enemy_id, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", {})
        for e in (enemies if isinstance(enemies, list) else []):
            if isinstance(e, dict) and e.get("id") == enemy_id:
                # Fall back to lower elevation or adjacent card
                pos = e.get("position")
                if pos is not None:
                    e["position"] = max(0, pos - 1)
                    gd.setdefault("markers", []).append({"type": "enemy_fallback", "enemy_id": enemy_id, "new_position": e["position"]})
                    return True
        return False

    def get_enemy_priority(self, enemy):
        # Returns priority for enemy actions (higher = more urgent)
        if not isinstance(enemy, dict):
            return 0
        strength = enemy.get("strength", "squad")
        priority = {"squad": 1, "platoon": 2, "company": 3}.get(strength, 1)
        if enemy.get("type") == "tank":
            priority += 2
        return priority

    def sort_enemies_by_priority(self, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        return sorted(enemies, key=self.get_enemy_priority, reverse=True)

    def place_enemy_mine(self, position, mine_type="ap", game_data=None):
        gd = game_data or {}
        mine = {"id": "enemy_mine_" + str(len(gd.get("enemy", []))), "type": "mine", "mine_type": mine_type, "position": position, "side": "enemy", "detonated": False}
        gd.setdefault("enemy", []).append(mine)
        gd.setdefault("markers", []).append({"type": "enemy_mine", "position": position, "mine_type": mine_type})
        return mine

    def place_enemy_leader(self, position, leader_type="nco", game_data=None):
        gd = game_data or {}
        leader = {"id": "enemy_leader_" + str(len(gd.get("enemy", []))), "type": "leader", "leader_type": leader_type, "position": position, "side": "enemy"}
        gd.setdefault("enemy", []).append(leader)
        # Leaders boost nearby enemy morale
        gd.setdefault("markers", []).append({"type": "enemy_leader", "position": position, "leader_type": leader_type})
        return leader

    def place_enemy_spotter(self, position, game_data=None):
        gd = game_data or {}
        spotter = {"id": "enemy_spotter_" + str(len(gd.get("enemy", []))), "type": "spotter", "position": position, "side": "enemy"}
        gd.setdefault("enemy", []).append(spotter)
        gd.setdefault("markers", []).append({"type": "enemy_spotter", "position": position})
        return spotter

    def trigger_fanaticism(self, enemy_id, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        for e in enemies:
            if isinstance(e, dict) and e.get("id") == enemy_id:
                e["fanatic"] = True
                e["morale"] = "fanatic"
                gd.setdefault("markers", []).append({"type": "fanaticism", "enemy_id": enemy_id})
                return True
        return False

    def trigger_human_wave(self, positions, game_data=None):
        gd = game_data or {}
        wave = {"type": "human_wave", "positions": positions, "resolved": False}
        for pos in positions:
            enemy = {"id": "human_wave_" + str(pos), "type": "infantry", "position": pos, "side": "enemy", "human_wave": True}
            gd.setdefault("enemy", []).append(enemy)
        gd.setdefault("markers", []).append(wave)
        return wave

    def capture_prisoner(self, enemy_id, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        for e in enemies:
            if isinstance(e, dict) and e.get("id") == enemy_id:
                e["captured"] = True
                e["status"] = "prisoner"
                gd.setdefault("prisoners", []).append(enemy_id)
                gd.setdefault("markers", []).append({"type": "prisoner", "enemy_id": enemy_id})
                return True
        return False

    def get_prisoners(self, game_data=None):
        gd = game_data or {}
        return gd.get("prisoners", [])

    def get_enemy_leaders(self, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        return [e for e in enemies if isinstance(e, dict) and e.get("type") == "leader"]

    def get_enemy_spotters(self, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        return [e for e in enemies if isinstance(e, dict) and e.get("type") == "spotter"]

    def get_enemy_mines(self, game_data=None):
        gd = game_data or {}
        enemies = gd.get("enemy", [])
        return [e for e in enemies if isinstance(e, dict) and e.get("type") == "mine"]

    def set_limited_visibility(self, limited, game_data=None):
        gd = game_data or {}
        vis = gd.setdefault("visibility", {})
        vis["limited"] = limited
        return limited

    def is_night(self, game_data=None):
        gd = game_data or {}
        vis = gd.get("visibility", {})
        return vis.get("limited", False)

    def set_illumination(self, position, game_data=None):
        gd = game_data or {}
        vis = gd.setdefault("visibility", {})
        vis["illumination"] = position
        gd.setdefault("markers", []).append({"type": "illumination", "position": position})
        return position

    def get_illumination(self, game_data=None):
        gd = game_data or {}
        vis = gd.get("visibility", {})
        return vis.get("illumination")

    def set_night_observation(self, enabled, game_data=None):
        gd = game_data or {}
        vis = gd.setdefault("visibility", {})
        vis["night_observation"] = enabled
        return enabled

    def has_night_observation(self, game_data=None):
        gd = game_data or {}
        vis = gd.get("visibility", {})
        return vis.get("night_observation", False)

    def los_range_limited(self, game_data=None):
        # In limited visibility, LOS range is reduced to adjacent cards only
        gd = game_data or {}
        vis = gd.get("visibility", {})
        if vis.get("limited", False):
            if vis.get("night_observation", False):
                return 2  # NODs extend to 2 cards
            if vis.get("illumination") is not None:
                return 3  # Illumination extends to 3 cards
            return 1  # Default limited visibility: adjacent only
        return 99  # Unlimited in daylight

    def can_see_in_limited_visibility(self, from_pos, to_pos, game_data=None):
        gd = game_data or {}
        vis = gd.get("visibility", {})
        if not vis.get("limited", False):
            return True
        map_data = gd.get("map", {})
        cols = map_data.get("cols", 4)
        if cols and from_pos is not None and to_pos is not None:
            from_r, from_c = divmod(from_pos, cols)
            to_r, to_c = divmod(to_pos, cols)
            distance = abs(from_r - to_r) + abs(from_c - to_c)
            max_range = self.los_range_limited(gd)
            if distance > max_range:
                return False
        return True

    def communication_range_limited(self, game_data=None):
        # In limited visibility, communication is restricted
        gd = game_data or {}
        vis = gd.get("visibility", {})
        if vis.get("limited", False):
            return "visual_verbal_only"  # Only same/adjacent card
        return "all"

    def vehicle_move_command(self, vehicle_id, from_pos, to_pos, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        vehicles = company.get("vehicles", [])
        vehicle = None
        for v in vehicles:
            if v.get("id") == vehicle_id:
                vehicle = v
                break
        if not vehicle:
            return {"moved": False, "reason": "vehicle not found"}
        vtype = vehicle.get("type", "unknown")
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if not (0 <= to_pos < len(cards)):
            return {"moved": False, "reason": "invalid position"}
        # Check trafficability
        card_id = cards[to_pos] if to_pos < len(cards) else None
        if card_id:
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data = get_card(card_id)
            if card_data:
                tc = terrain_card(card_data.get("terrain_type", "open_field"), card_id)
                traffic = tc.get("trafficability", "good")
                if not self.vehicle_can_move_to(vtype, traffic):
                    return {"moved": False, "reason": "terrain not trafficable"}
        # Move vehicle
        vehicle["position"] = to_pos
        # Move embarked units with vehicle
        for uid in vehicle.get("embarked", []):
            for u in company.get("units", []):
                if u.get("id") == uid:
                    u["position"] = to_pos
        gd.setdefault("markers", []).append({"type": "vehicle_move", "vehicle_id": vehicle_id, "from": from_pos, "to": to_pos})
        return {"moved": True, "vehicle_id": vehicle_id, "position": to_pos}

    def get_embarked_units(self, vehicle_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        vehicles = company.get("vehicles", [])
        for v in vehicles:
            if v.get("id") == vehicle_id:
                return v.get("embarked", [])
        return []

    def vehicle_transport_capacity(self, vehicle_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        vehicles = company.get("vehicles", [])
        for v in vehicles:
            if v.get("id") == vehicle_id:
                stats = self.get_vehicle_stats(v.get("type", "unknown"))
                capacity = stats.get("capacity", 0)
                embarked = len(v.get("embarked", []))
                return {"capacity": capacity, "embarked": embarked, "available": capacity - embarked}
        return {"capacity": 0, "embarked": 0, "available": 0}

    def disembark_all(self, vehicle_id, position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        vehicles = company.get("vehicles", [])
        for v in vehicles:
            if v.get("id") == vehicle_id:
                embarked = v.get("embarked", [])
                for uid in list(embarked):
                    self.disembark_unit(uid, position, gd)
                v["embarked"] = []
                return len(embarked)
        return 0

    def resolve_at_combat(self, attacker_weapon, target_vehicle_type, range_distance, game_data=None):
        gd = game_data or {}
        # AT combat: recoilless rifles, AT guns, etc. vs vehicles
        weapon_stats = self.get_weapon_stats(attacker_weapon)
        weapon_range = weapon_stats.get("range", 4)
        if range_distance > weapon_range:
            return {"resolved": False, "reason": "out of range"}
        vof_rating = weapon_stats.get("vof_rating", "C")
        # Resolve VOF vs vehicle
        result = self.resolve_vof_vs_vehicle(vof_rating, target_vehicle_type)
        # Consume ammo
        ammo_type = weapon_stats.get("ammo_type", "none")
        if ammo_type != "none":
            ammo = gd.setdefault("company", {}).setdefault("ammo", {})
            if ammo.get(ammo_type, 0) <= 0:
                return {"resolved": False, "reason": "no ammo"}
            ammo[ammo_type] = max(0, ammo.get(ammo_type, 0) - 1)
        gd.setdefault("markers", []).append({"type": "at_combat", "weapon": attacker_weapon, "target": target_vehicle_type, "result": result, "resolved": True})
        return {"resolved": True, "weapon": attacker_weapon, "target": target_vehicle_type, "result": result, "range": range_distance}

    def resolve_reaction_fire(self, trigger_pos, reactor_pos, game_data=None):
        gd = game_data or {}
        # Reaction fire: unit fires when enemy moves into LOS
        los_ok, reason = self.has_los(trigger_pos, reactor_pos, game_data=gd)
        if not los_ok:
            return {"fired": False, "reason": "no LOS"}
        # Check if reactor has VOF marker
        vof = self.get_vof_at(reactor_pos, gd)
        if vof:
            result = self.resolve_fire(reactor_pos, trigger_pos, vof.get("rating", "C"), game_data=gd)
            gd.setdefault("markers", []).append({"type": "reaction_fire", "trigger": trigger_pos, "reactor": reactor_pos, "result": result})
            return {"fired": True, "result": result}
        return {"fired": False, "reason": "no VOF marker"}

    def at_weapon_types(self):
        return ["rcl", "at_gun", "bazooka", "rpg", "tow"]

    def is_at_weapon(self, weapon_type):
        return weapon_type in self.at_weapon_types() or weapon_type in ("rcl",)

    def load_helicopter(self, helicopter_id, unit_ids, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        helicopters = company.get("helicopters", [])
        units = company.get("units", [])
        heli = None
        for h in helicopters:
            if h.get("id") == helicopter_id:
                heli = h
                break
        if not heli:
            return {"loaded": False, "reason": "helicopter not found"}
        capacity = heli.get("capacity", 8)
        loaded = heli.setdefault("loaded_units", [])
        if len(loaded) + len(unit_ids) > capacity:
            return {"loaded": False, "reason": "exceeds capacity"}
        for uid in unit_ids:
            for u in units:
                if u.get("id") == uid:
                    loaded.append(uid)
                    u["embarked_in"] = helicopter_id
                    u["position"] = None
                    break
        gd.setdefault("markers", []).append({"type": "helicopter_load", "helicopter_id": helicopter_id, "units": unit_ids})
        return {"loaded": True, "helicopter_id": helicopter_id, "units": unit_ids, "total_loaded": len(loaded)}

    def land_helicopter(self, helicopter_id, position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        helicopters = company.get("helicopters", [])
        heli = None
        for h in helicopters:
            if h.get("id") == helicopter_id:
                heli = h
                break
        if not heli:
            return {"landed": False, "reason": "helicopter not found"}
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if not (0 <= position < len(cards)):
            return {"landed": False, "reason": "invalid position"}
        # Check landing zone
        card_id = cards[position] if position < len(cards) else None
        if card_id:
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data = get_card(card_id)
            if card_data:
                tc = terrain_card(card_data.get("terrain_type", "open_field"), card_id)
                if not tc.get("landing_zone", False):
                    return {"landed": False, "reason": "not a landing zone"}
        heli["position"] = position
        # Disembark loaded units
        for uid in heli.get("loaded_units", []):
            for u in company.get("units", []):
                if u.get("id") == uid:
                    u["position"] = position
                    u["embarked_in"] = None
        heli["loaded_units"] = []
        gd.setdefault("markers", []).append({"type": "helicopter_landing", "helicopter_id": helicopter_id, "position": position})
        return {"landed": True, "helicopter_id": helicopter_id, "position": position}

    def set_landing_zone(self, position, game_data=None):
        gd = game_data or {}
        zones = gd.setdefault("landing_zones", [])
        if position not in zones:
            zones.append(position)
        return zones

    def is_landing_zone(self, position, game_data=None):
        gd = game_data or {}
        zones = gd.get("landing_zones", [])
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if position < len(cards):
            card_id = cards[position]
            if card_id:
                from app.games.fields_of_fire.terrain import terrain_card, get_card
                card_data = get_card(card_id)
                if card_data:
                    tc = terrain_card(card_data.get("terrain_type", "open_field"), card_id)
                    if tc.get("landing_zone", False):
                        return True
        return position in zones

    def loiter_helicopter(self, helicopter_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        helicopters = company.get("helicopters", [])
        for h in helicopters:
            if h.get("id") == helicopter_id:
                h["loitering"] = True
                gd.setdefault("markers", []).append({"type": "helicopter_loiter", "helicopter_id": helicopter_id})
                return True
        return False

    def get_helicopter_at(self, position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        helicopters = company.get("helicopters", [])
        for h in helicopters:
            if h.get("position") == position:
                return h
        return None

    def plan_air_assault(self, helicopter_id, landing_zone, units, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        helicopters = company.get("helicopters", [])
        heli = None
        for h in helicopters:
            if h.get("id") == helicopter_id:
                heli = h
                break
        if not heli:
            return {"planned": False, "reason": "helicopter not found"}
        # Check landing zone
        if not self.is_landing_zone(landing_zone, gd):
            return {"planned": False, "reason": "not a landing zone"}
        assault = {
            "type": "air_assault",
            "helicopter_id": helicopter_id,
            "landing_zone": landing_zone,
            "units": units,
            "status": "planned",
        }
        gd.setdefault("assault_waves", []).append(assault)
        gd.setdefault("markers", []).append({"type": "air_assault_plan", "helicopter_id": helicopter_id, "landing_zone": landing_zone})
        return {"planned": True, "assault": assault}

    def execute_air_assault(self, assault_index, game_data=None):
        gd = game_data or {}
        waves = gd.get("assault_waves", [])
        if assault_index >= len(waves):
            return {"executed": False, "reason": "invalid assault index"}
        assault = waves[assault_index]
        if assault.get("status") != "planned":
            return {"executed": False, "reason": "assault not planned"}
        # Execute: load units and land
        heli_id = assault.get("helicopter_id")
        lz = assault.get("landing_zone")
        units = assault.get("units", [])
        self.load_helicopter(heli_id, units, gd)
        self.land_helicopter(heli_id, lz, gd)
        assault["status"] = "executed"
        gd.setdefault("markers", []).append({"type": "air_assault_executed", "helicopter_id": heli_id, "landing_zone": lz})
        return {"executed": True, "assault": assault}

    def plan_amphibious_assault(self, landing_position, units, support, game_data=None):
        gd = game_data or {}
        assault = {
            "type": "amphibious_assault",
            "landing_position": landing_position,
            "units": units,
            "support": support,
            "status": "planned",
        }
        gd.setdefault("assault_waves", []).append(assault)
        gd.setdefault("markers", []).append({"type": "amphibious_assault_plan", "position": landing_position})
        return {"planned": True, "assault": assault}

    def execute_amphibious_assault(self, assault_index, game_data=None):
        gd = game_data or {}
        waves = gd.get("assault_waves", [])
        if assault_index >= len(waves):
            return {"executed": False, "reason": "invalid assault index"}
        assault = waves[assault_index]
        if assault.get("type") != "amphibious_assault":
            return {"executed": False, "reason": "not an amphibious assault"}
        if assault.get("status") != "planned":
            return {"executed": False, "reason": "assault not planned"}
        # Place units at landing position
        pos = assault.get("landing_position")
        for uid in assault.get("units", []):
            for u in gd.get("company", {}).get("units", []):
                if u.get("id") == uid:
                    u["position"] = pos
                    break
        assault["status"] = "executed"
        gd.setdefault("markers", []).append({"type": "amphibious_assault_executed", "position": pos})
        return {"executed": True, "assault": assault}

    def get_assault_waves(self, game_data=None):
        gd = game_data or {}
        return gd.get("assault_waves", [])

    def get_pending_assaults(self, game_data=None):
        gd = game_data or {}
        waves = gd.get("assault_waves", [])
        return [w for w in waves if w.get("status") == "planned"]

    def cancel_assault(self, assault_index, game_data=None):
        gd = game_data or {}
        waves = gd.get("assault_waves", [])
        if assault_index >= len(waves):
            return False
        waves[assault_index]["status"] = "cancelled"
        return True

    SKILLS = ["leadership", "tactics", "weapons", "communication", "medical", "engineering"]

    def gain_experience(self, amount, game_data=None):
        gd = game_data or {}
        company = gd.setdefault("company", {})
        company["experience"] = company.get("experience", 0) + amount
        company["experience_points"] = company.get("experience_points", 0) + amount
        return company["experience"]

    def spend_experience(self, skill, cost=1, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        exp = company.get("experience", 0)
        if exp < cost:
            return False
        company["experience"] = exp - cost
        skills = company.setdefault("skills", [])
        if skill not in skills:
            skills.append(skill)
        return True

    def get_experience(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        return company.get("experience", 0)

    def get_skills(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        return company.get("skills", [])

    def has_skill(self, skill, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        skills = company.get("skills", [])
        return skill in skills

    def request_replacements(self, count=1, game_data=None):
        gd = game_data or {}
        company = gd.setdefault("company", {})
        campaign = gd.setdefault("campaign", {})
        # Replacements available based on campaign progress
        available = campaign.get("replacements_available", 0)
        if available < count:
            return {"requested": False, "reason": "not enough replacements available", "available": available}
        campaign["replacements_available"] = available - count
        company["replacements"] = company.get("replacements", 0) + count
        gd.setdefault("markers", []).append({"type": "replacement_request", "count": count})
        return {"requested": True, "count": count, "remaining": campaign["replacements_available"]}

    def complete_mission(self, mission_id, outcome, game_data=None):
        gd = game_data or {}
        campaign = gd.setdefault("campaign", {})
        missions = campaign.setdefault("missions_completed", [])
        if mission_id not in missions:
            missions.append(mission_id)
        campaign["missions_completed"] = missions
        # Award experience for mission completion
        if outcome == "victory":
            self.gain_experience(5, gd)
            campaign["experience"] = campaign.get("experience", 0) + 5
        elif outcome == "partial":
            self.gain_experience(2, gd)
            campaign["experience"] = campaign.get("experience", 0) + 2
        # Update company campaign tracking
        company = gd.setdefault("company", {})
        company["campaign_missions_completed"] = len(missions)
        if len(missions) >= 5:
            company["campaign_won"] = True
            gd["phase"] = "game_over"
        return {"mission_id": mission_id, "outcome": outcome, "missions_completed": len(missions)}

    def get_campaign_status(self, game_data=None):
        gd = game_data or {}
        campaign = gd.get("campaign", {})
        company = gd.get("company", {})
        return {
            "missions_completed": campaign.get("missions_completed", []),
            "experience": campaign.get("experience", 0),
            "replacements_available": campaign.get("replacements_available", 0),
            "campaign_won": company.get("campaign_won", False),
        }

    def check_campaign_victory(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        if company.get("campaign_won", False):
            return "player_1"
        campaign = gd.get("campaign", {})
        missions = campaign.get("missions_completed", [])
        if isinstance(missions, int):
            missions = [missions] if missions > 0 else []
        if len(missions) >= 5:
            return "player_1"
        return None

    def get_available_skills(self):
        return self.SKILLS

    def enter_building(self, unit_id, building_position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        urban = gd.setdefault("urban", {})
        buildings = urban.setdefault("buildings", [])
        for u in units:
            if u.get("id") == unit_id:
                u["position"] = building_position
                u["in_building"] = True
                if building_position not in buildings:
                    buildings.append(building_position)
                gd.setdefault("markers", []).append({"type": "enter_building", "unit_id": unit_id, "position": building_position})
                return True
        return False

    def exit_building(self, unit_id, position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        for u in units:
            if u.get("id") == unit_id:
                u["position"] = position
                u["in_building"] = False
                gd.setdefault("markers", []).append({"type": "exit_building", "unit_id": unit_id, "position": position})
                return True
        return False

    def breach_building(self, position, game_data=None):
        gd = game_data or {}
        urban = gd.setdefault("urban", {})
        breached = urban.setdefault("breached", [])
        if position not in breached:
            breached.append(position)
        gd.setdefault("markers", []).append({"type": "breach", "position": position})
        return True

    def occupy_rooftop(self, unit_id, building_position, game_data=None):
        gd = game_data or {}
        urban = gd.setdefault("urban", {})
        rooftops = urban.setdefault("rooftops", [])
        if building_position not in rooftops:
            rooftops.append(building_position)
        company = gd.get("company", {})
        units = company.get("units", [])
        for u in units:
            if u.get("id") == unit_id:
                u["position"] = building_position
                u["on_rooftop"] = True
                gd.setdefault("markers", []).append({"type": "rooftop", "unit_id": unit_id, "position": building_position})
                return True
        return False

    def barricade_position(self, position, game_data=None):
        gd = game_data or {}
        urban = gd.setdefault("urban", {})
        barricades = urban.setdefault("barricades", [])
        if position not in barricades:
            barricades.append(position)
        gd.setdefault("markers", []).append({"type": "barricade", "position": position})
        return True

    def is_in_building(self, unit_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        for u in units:
            if u.get("id") == unit_id:
                return u.get("in_building", False)
        return False

    def is_on_rooftop(self, unit_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        units = company.get("units", [])
        for u in units:
            if u.get("id") == unit_id:
                return u.get("on_rooftop", False)
        return False

    def urban_combat_modifier(self, position, game_data=None):
        gd = game_data or {}
        urban = gd.get("urban", {})
        buildings = urban.get("buildings", [])
        breached = urban.get("breached", [])
        barricades = urban.get("barricades", [])
        modifier = 0
        if position in buildings:
            if position in breached:
                modifier = -1  # Breached building provides less cover
            else:
                modifier = 2  # Building provides cover
        if position in barricades:
            modifier += 1  # Barricade adds cover
        return modifier

    def get_buildings(self, game_data=None):
        gd = game_data or {}
        urban = gd.get("urban", {})
        return urban.get("buildings", [])

    def get_breached_buildings(self, game_data=None):
        gd = game_data or {}
        urban = gd.get("urban", {})
        return urban.get("breached", [])

    _SCENARIO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs", "fof", "fields_of_fire_scenarios.json")

    def load_scenarios_full(self):
        path = os.path.normpath(self._SCENARIO_PATH)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def load_scenarios(self):
        path = os.path.normpath(self._SCENARIO_PATH)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            result = {}
            for camp_id, camp in data.get("campaigns", {}).items():
                for sid, scenario in camp.get("scenarios", {}).items():
                    result[sid] = scenario
            result.update(data.get("scenarios", {}))
            return result
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get_scenario(self, scenario_id):
        scenarios = self.load_scenarios()
        return scenarios.get(scenario_id)

    def load_campaigns(self):
        path = os.path.normpath(self._SCENARIO_PATH)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("campaigns", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def list_campaigns(self):
        return list(self.load_campaigns().keys())

    def get_campaign(self, campaign_id):
        return self.load_campaigns().get(campaign_id)

    def get_campaign_scenarios(self, campaign_id):
        camp = self.get_campaign(campaign_id)
        if not camp:
            return {}
        return camp.get("scenarios", {})

    def list_scenarios(self):
        scenarios = self.load_scenarios()
        return list(scenarios.keys())

    def validate_scenario(self, scenario_id):
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return False, "scenario not found"
        required = ["scenario_id", "name", "map_layout", "victory_conditions"]
        for field in required:
            if field not in scenario:
                return False, "missing field: " + field
        return True, "ok"

    def get_scenario_deployment_zones(self, scenario_id):
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return []
        return scenario.get("deployment_zones", [])

    def get_scenario_victory_conditions(self, scenario_id):
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return None
        return scenario.get("victory_conditions")

    def load_mission_map(self, scenario_id, game_data=None):
        gd = game_data or {}
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return {"loaded": False, "reason": "scenario not found"}
        map_layout = scenario.get("map_layout", {})
        rows = map_layout.get("rows", 3)
        cols = map_layout.get("cols", 4)
        gd.setdefault("map", {})
        gd["map"]["rows"] = rows
        gd["map"]["cols"] = cols
        gd["map"]["cards"] = [None] * (rows * cols)
        # Load terrain decks
        decks = map_layout.get("terrain_decks", [])
        gd["map"]["card_layout"] = map_layout.get("card_layout")
        # Card layout
        card_layout = map_layout.get("card_layout")
        if card_layout and isinstance(card_layout, list):
            if any(isinstance(i, dict) for i in card_layout):
                cards = [None] * (rows * cols)
                for item in card_layout:
                    if isinstance(item, dict):
                        r = item.get("row")
                        c = item.get("col")
                        cid = item.get("id")
                        if r is not None and c is not None:
                            idx = int(r) * cols + int(c)
                            if 0 <= idx < len(cards):
                                cards[idx] = cid
                gd["map"]["cards"] = cards
                gd["deployment_zones"] = []
                for item in card_layout:
                    if isinstance(item, dict) and item.get("deployment_zone"):
                        r = item.get("row")
                        c = item.get("col")
                        if r is not None and c is not None:
                            idx = int(r) * cols + int(c)
                            gd["deployment_zones"].append(idx)
            else:
                gd["map"]["cards"] = card_layout[:rows * cols]
                while len(gd["map"]["cards"]) < rows * cols:
                    gd["map"]["cards"].append(None)
        gd.setdefault("markers", []).append({"type": "map_loaded", "scenario": scenario_id, "rows": rows, "cols": cols})
        return {"loaded": True, "rows": rows, "cols": cols, "decks": decks}

    def get_terrain_deck_cards(self, deck_name):
        from app.games.fields_of_fire.terrain import get_deck
        return get_deck(deck_name)

    def draw_mission_cards(self, deck_name, count, game_data=None):
        gd = game_data or {}
        from app.games.fields_of_fire.terrain import get_deck
        deck = get_deck(deck_name)
        if not deck:
            return []
        # Draw cards from deck
        drawn = deck[:count]
        # Track drawn cards
        gd.setdefault("drawn_cards", []).extend([c.get("card_id") for c in drawn])
        return drawn

    def place_mission_card(self, position, card_id, game_data=None):
        gd = game_data or {}
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if not (0 <= position < len(cards)):
            return False
        cards[position] = card_id
        gd.setdefault("markers", []).append({"type": "card_placed", "position": position, "card_id": card_id})
        return True

    def get_map_layout(self, game_data=None):
        gd = game_data or {}
        map_data = gd.get("map", {})
        return {
            "rows": map_data.get("rows", 3),
            "cols": map_data.get("cols", 4),
            "cards": map_data.get("cards", []),
            "decks": map_data.get("decks", []),
        }

    def mark_deployment_zones(self, zones, game_data=None):
        gd = game_data or {}
        gd["deployment_zones"] = zones
        gd.setdefault("markers", []).append({"type": "deployment_zones", "zones": zones})
        return zones

    def get_deployment_zones(self, game_data=None):
        gd = game_data or {}
        return gd.get("deployment_zones", [])

    def is_deployment_zone(self, position, game_data=None):
        gd = game_data or {}
        zones = gd.get("deployment_zones", [])
        return position in zones

    def validate_deployment(self, unit_id, position, game_data=None):
        gd = game_data or {}
        # During setup, units must be placed in deployment zones if defined
        zones = gd.get("deployment_zones", [])
        if zones and position not in zones:
            return False, "position not in deployment zone"
        return True, "ok"

    def get_deployment_zone_units(self, game_data=None):
        gd = game_data or {}
        zones = gd.get("deployment_zones", [])
        company = gd.get("company", {})
        units = company.get("units", [])
        zone_units = {}
        for z in zones:
            zone_units[z] = [u for u in units if u.get("position") == z]
        return zone_units

    def is_setup_complete(self, game_data=None):
        gd = game_data or {}
        issues = []
        # Check map is laid out
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if not cards or all(c is None for c in cards):
            issues.append("map not laid out")
        # Check units are placed
        company = gd.get("company", {})
        units = company.get("units", [])
        unplaced = [u for u in units if u.get("position") is None]
        if unplaced:
            issues.append(f"{len(unplaced)} units not placed")
        # Check vehicles placed
        vehicles = company.get("vehicles", [])
        unplaced_v = [v for v in vehicles if v.get("position") is None]
        if unplaced_v:
            issues.append(f"{len(unplaced_v)} vehicles not placed")
        if issues:
            return False, "; ".join(issues)
        return True, "setup complete"

    def get_setup_status(self, game_data=None):
        gd = game_data or {}
        complete, reason = self.is_setup_complete(gd)
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        company = gd.get("company", {})
        units = company.get("units", [])
        placed_units = [u for u in units if u.get("position") is not None]
        return {
            "complete": complete,
            "reason": reason,
            "map_laid_out": bool(cards) and not all(c is None for c in cards),
            "units_placed": len(placed_units),
            "units_total": len(units),
            "vehicles_placed": len([v for v in company.get("vehicles", []) if v.get("position") is not None]),
            "vehicles_total": len(company.get("vehicles", [])),
        }

    def evaluate_victory_conditions(self, game_data=None):
        gd = game_data or {}
        conditions = gd.get("victory_conditions")
        if not conditions:
            return None
        cond_type = conditions.get("type", "")
        target = conditions.get("target")
        if cond_type == "reach_position":
            # Check if any unit reached target position
            company = gd.get("company", {})
            units = company.get("units", [])
            for u in units:
                if u.get("position") == target:
                    return "player_1"
        elif cond_type == "eliminate_enemies":
            enemies = gd.get("enemy", [])
            if len(enemies) == 0:
                return "player_1"
        elif cond_type == "hold_position":
            # Check if player holds target position
            company = gd.get("company", {})
            units = company.get("units", [])
            for u in units:
                if u.get("position") == target:
                    return "player_1"
        elif cond_type == "complete_missions":
            campaign = gd.get("campaign", {})
            missions = campaign.get("missions_completed", [])
            if isinstance(missions, int):
                missions = [missions] if missions > 0 else []
            if len(missions) >= (target or 1):
                return "player_1"
        elif cond_type == "survive_turns":
            turn = gd.get("turn", 0)
            if turn >= (target or 10):
                return "player_1"
        return None

    def check_victory(self, game_data=None):
        gd = game_data or {}
        # Check phase-based victory
        if gd.get("phase") == "game_over":
            return gd.get("current_player", "player_1")
        # Check campaign victory
        campaign_winner = self.check_campaign_victory(gd)
        if campaign_winner:
            return campaign_winner
        # Check scenario victory conditions
        scenario_winner = self.evaluate_victory_conditions(gd)
        if scenario_winner:
            gd["phase"] = "game_over"
            return scenario_winner
        return None

    def check_win(self, state: dict[str, Any]) -> str | None:
        gd = state.get("game_data", {})
        return self.check_victory(gd)

    def get_command_radius(self, hq_id, game_data=None):
        gd = game_data or {}
        if hq_id.startswith("bn_"):
            return 3
        elif hq_id.startswith("co_") and not hq_id.startswith("co_staff"):
            return 2
        elif hq_id.startswith("plt_"):
            return 1
        return 1

    def get_activated_hqs(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        command = company.get("command", {})
        return command.get("activated", [])

    def activate_hq_with_radius(self, hq_id, game_data=None):
        gd = game_data or {}
        company = gd.setdefault("company", {})
        command = company.setdefault("command", {})
        activated = command.setdefault("activated", [])
        if hq_id not in activated:
            activated.append(hq_id)
        return {"hq_id": hq_id, "radius": self.get_command_radius(hq_id, gd)}

    def get_hq_casualties(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        casualties = company.get("casualties", [])
        hq_casualties = []
        for c in casualties:
            if isinstance(c, dict) and c.get("type") == "hq":
                hq_casualties.append(c.get("id"))
            elif isinstance(c, str) and c.startswith(("bn_", "co_", "plt_")):
                hq_casualties.append(c)
        return hq_casualties

    def request_hq_replacement(self, hq_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        replacements = company.get("replacements", 0)
        if replacements > 0:
            company["replacements"] = replacements - 1
            return True
        return False

    def get_activation_sequence(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        command = company.get("command", {})
        seq = []
        if command.get("bn_hq"):
            seq.append(command["bn_hq"])
        if command.get("co_hq"):
            seq.append(command["co_hq"])
        for plt in command.get("plt_hqs", []):
            seq.append(plt)
        for staff in command.get("co_staff", []):
            seq.append(staff)
        return seq

    def can_activate_hq(self, hq_id, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        command = company.get("command", {})
        activated = command.get("activated", [])
        if hq_id in activated:
            return False, "already activated"
        seq = self.get_activation_sequence(gd)
        idx = seq.index(hq_id) if hq_id in seq else -1
        if idx == -1:
            return False, "unknown HQ"
        for i in range(idx):
            if seq[i] not in activated:
                return False, "previous HQ not activated"
        return True, "ok"

    def draw_commands_for_activated(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        command = company.get("command", {})
        activated = command.get("activated", [])
        total = max(1, len(activated) * 2)
        command["commands_pool"] = command.get("commands_pool", 0) + total
        command["command_draw"] = command.get("command_draw", []) + [total]
        return total

    def spend_command_points(self, amount, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        command = company.get("command", {})
        pool = command.get("commands_pool", 0)
        if amount <= 0 or amount > pool:
            return False
        command["commands_pool"] = pool - amount
        return True

    def reset_turn_activation(self, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        command = company.get("command", {})
        command["activated"] = []
        return True

    def can_communicate(self, originator, recipient, game_data=None):
        if not originator or not recipient:
            return False
        gd = game_data or {}
        vis = gd.get("visibility", {})
        limited = vis.get("limited", False)
        origin_pos = originator.get("position")
        recip_pos = recipient.get("position")

        if origin_pos is not None and recip_pos is not None and origin_pos == recip_pos:
            return True

        if not limited and origin_pos is not None and recip_pos is not None:
            rows = gd.get("map", {}).get("rows", 0)
            cols = gd.get("map", {}).get("cols", 0)
            if cols:
                o_r, o_c = divmod(origin_pos, cols)
                r_r, r_c = divmod(recip_pos, cols)
                if abs(o_r - r_r) <= 1 and abs(o_c - r_c) <= 1:
                    return True
            if abs(origin_pos - recip_pos) <= 1:
                return True

        if originator.get("type") == "runner" or recipient.get("type") == "runner":
            return True

        networks = gd.get("company", {}).get("networks", {})
        radios = networks.get("radios", [])
        for radio in radios:
            if radio.get("damaged"):
                continue
            radio_type = radio.get("type", "")
            if radio_type == "scr536":
                if origin_pos is not None and recip_pos is not None and abs(origin_pos - recip_pos) <= 1:
                    return True
            elif radio_type in ("scr300", "scr610"):
                return True

        phones = networks.get("phones", [])
        for phone in phones:
            if not phone.get("damaged") and phone.get("wired"):
                return True

        return False

    def create_runner(self, runner_id, game_data=None):
        gd = game_data or {}
        company = gd.setdefault("company", {})
        runners = company.setdefault("runners", [])
        runner = {"id": runner_id, "type": "runner", "position": None, "dispatched": False, "arrived": False}
        runners.append(runner)
        return runner

    def dispatch_runner(self, runner_id, target_position, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        runners = company.get("runners", [])
        for r in runners:
            if r.get("id") == runner_id:
                r["dispatched"] = True
                r["target_position"] = target_position
                r["position"] = target_position
                return True
        return False

    def radio_range(self, radio_type):
        ranges = {"scr536": 1, "scr300": 3, "scr610": 10}
        return ranges.get(radio_type, 1)

    def lay_field_phone_wire(self, from_pos, to_pos, game_data=None):
        gd = game_data or {}
        company = gd.get("company", {})
        networks = company.setdefault("networks", {})
        phones = networks.setdefault("phones", [])
        phone = {"type": "field_phone", "from": from_pos, "to": to_pos, "wired": True, "damaged": False}
        phones.append(phone)
        return phone

    def is_limited_visibility(self, game_data=None):
        gd = game_data or {}
        vis = gd.get("visibility", {})
        return vis.get("limited", False)

    def get_elevation(self, card: dict[str, Any] | str) -> int:
        if isinstance(card, str):
            from app.games.fields_of_fire.terrain import terrain_card
            card = terrain_card(card)
        return card.get("elevation", 0) if isinstance(card, dict) else 0

    def get_cover(self, card) -> dict:
        if isinstance(card, str):
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data = get_card(card)
            if card_data:
                card = terrain_card(card_data.get("terrain_type", "open_field"), card)
            else:
                card = terrain_card(card)
        if isinstance(card, dict):
            return {
                "high": card.get("cover_high", 0),
                "low": card.get("cover_low", 0),
                "potential": card.get("cover_potential", 0),
            }
        return {"high": 0, "low": 0, "potential": 0}

    def get_cover_modifier(self, cover_value, target_type="infantry"):
        # Cover modifier for combat resolution (positive = harder to hit)
        if cover_value >= 3:
            return 2
        elif cover_value >= 2:
            return 1
        elif cover_value >= 1:
            return 0
        return -1

    def is_concealed(self, unit, game_data=None):
        gd = game_data or {}
        pos = unit.get("position")
        if pos is None:
            return False
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if pos >= len(cards):
            return False
        card_id = cards[pos]
        if not card_id:
            return False
        cover = self.get_cover(card_id)
        # Unit is concealed if in cover and not exposed
        if cover.get("high", 0) >= 2 or cover.get("low", 0) >= 2:
            if not unit.get("exposed", False):
                return True
        return False

    def degrade_cover(self, position, amount=1, game_data=None):
        gd = game_data or {}
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if position >= len(cards):
            return False
        card_id = cards[position]
        if not card_id:
            return False
        # Track cover degradation in markers
        gd.setdefault("markers", []).append({
            "type": "cover_degraded",
            "position": position,
            "amount": amount,
        })
        return True

    def get_concealment_bonus(self, unit, game_data=None):
        if self.is_concealed(unit, game_data):
            return 1
        return 0

    def has_los(self, card_a, card_b, unit_a=None, unit_b=None, game_data=None):
        from app.games.fields_of_fire.terrain import border_dark, card_borders
        # Get card objects
        if isinstance(card_a, str):
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data_a = get_card(card_a)
            if card_data_a and card_data_a.get('terrain_type'):
                ca = terrain_card(card_data_a['terrain_type'], card_a)
            else:
                ca = terrain_card('open_field', card_a)
        elif isinstance(card_a, dict):
            ca = card_a
        else:
            ca = {}

        if isinstance(card_b, str):
            from app.games.fields_of_fire.terrain import terrain_card, get_card
            card_data_b = get_card(card_b)
            if card_data_b and card_data_b.get('terrain_type'):
                cb = terrain_card(card_data_b['terrain_type'], card_b)
            else:
                cb = terrain_card('open_field', card_b)
        elif isinstance(card_b, dict):
            cb = card_b
        else:
            cb = {}

        # Same card always has LOS
        if card_a == card_b:
            return True, "same_card"

        # Elevation affects LOS
        elev_a = ca.get("elevation", 0) if isinstance(ca, dict) else 0
        elev_b = cb.get("elevation", 0) if isinstance(cb, dict) else 0
        borders_a = card_borders(ca)
        borders_b = card_borders(cb)

        # Dense terrain (all dark borders) blocks LOS unless viewer is on higher elevation
        all_dark_a = all(b.lower() == "dark" for b in borders_a)
        all_dark_b = all(b.lower() == "dark" for b in borders_b)
        if all_dark_a and elev_b <= elev_a:
            return False, "blocked by dense terrain"
        if all_dark_b and elev_a <= elev_b:
            return False, "blocked by dense terrain"

        # Dark borders on facing sides can block LOS
        dark_count_a = sum(1 for b in borders_a if b.lower() == "dark")
        dark_count_b = sum(1 for b in borders_b if b.lower() == "dark")
        if dark_count_a >= 3 and elev_b <= elev_a + 1:
            return False, "blocked by terrain"
        if dark_count_b >= 3 and elev_a <= elev_b + 1:
            return False, "blocked by terrain"

        # Buildings block LOS (unless viewer is on higher elevation)
        terrain_a = ca.get("type", "") if isinstance(ca, dict) else ""
        terrain_b = cb.get("type", "") if isinstance(cb, dict) else ""
        if "building" in terrain_a.lower() or "urban" in terrain_a.lower():
            if elev_b <= elev_a:
                return False, "blocked by building"
        if "building" in terrain_b.lower() or "urban" in terrain_b.lower():
            if elev_a <= elev_b:
                return False, "blocked by building"

        # Smoke markers block LOS
        gd = game_data or {}
        smoke_markers = gd.get("smoke_markers", [])
        smoke_positions = [m.get("position") for m in smoke_markers if isinstance(m, dict)]
        # Check if either card has smoke
        card_a_pos = None
        card_b_pos = None
        if isinstance(card_a, int):
            card_a_pos = card_a
        if isinstance(card_b, int):
            card_b_pos = card_b
        # If we have game_data with map, check smoke on cards
        map_data = gd.get("map", {})
        cards = map_data.get("cards", [])
        if card_a_pos is not None and card_a_pos in smoke_positions:
            return False, "blocked by smoke"
        if card_b_pos is not None and card_b_pos in smoke_positions:
            return False, "blocked by smoke"

        # Elevation difference too great blocks LOS
        if abs(elev_a - elev_b) > 3:
            return False, "blocked by elevation"

        return True, "clear"


