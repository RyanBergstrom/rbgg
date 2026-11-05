"""Core validator-owned rules state machine for Bus."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.legal_move_interface import LegalMoveValidator
from app.core.rng import create_rng

BUILDING_TYPES = ("house", "office", "pub")
BUILDING_TILES_PER_TYPE = 30
MAX_LINE_MARKERS_PER_PLAYER = 25
ACTION_TYPES = (
    "line_expansion", "buses", "passengers", "buildings", "clock",
    "vrrooomm", "starting_player",
)
ACTION_SLOT_LIMITS = {
    "line_expansion": 6,
    "buses": 1,
    "passengers": 6,
    "buildings": 6,
    "clock": 1,
    "vrrooomm": 6,
    "starting_player": 1,
}
RESOLUTION_PHASES = {
    "line_expansion": "RESOLVE_LINE_EXPANSION",
    "buses": "RESOLVE_BUSES",
    "passengers": "RESOLVE_PASSENGERS",
    "buildings": "RESOLVE_BUILDINGS",
    "clock": "RESOLVE_CLOCK",
    "vrrooomm": "RESOLVE_VRROOMM",
    "starting_player": "RESOLVE_STARTING_PLAYER",
}

# Canonical board topology. Coordinates are percentages of the supplied board
# artwork and remain presentation metadata; rule legality uses only IDs/edges.
NODES = {
    "c1": {"x": 16.9, "y": 7.8}, "c2": {"x": 26.9, "y": 4.2},
    "c3": {"x": 12.8, "y": 20.7}, "c4": {"x": 24.9, "y": 20.4, "station": True},
    "c5": {"x": 35.8, "y": 11.7}, "c6": {"x": 46.6, "y": 16.4},
    "c7": {"x": 58.3, "y": 11.7}, "c8": {"x": 66.6, "y": 23.3},
    "c9": {"x": 37.0, "y": 25.3}, "c10": {"x": 56.2, "y": 25.6},
    "c11": {"x": 16.6, "y": 33.8}, "c12": {"x": 29.1, "y": 34.8},
    "c13": {"x": 47.3, "y": 31.6}, "c14": {"x": 62.7, "y": 38.2},
    "c15": {"x": 39.7, "y": 40.3}, "c16": {"x": 50.2, "y": 46.6},
    "c17": {"x": 22.2, "y": 44.4}, "c18": {"x": 12.1, "y": 51.0},
    "c19": {"x": 32.4, "y": 50.4}, "c20": {"x": 58.8, "y": 50.4},
    "c21": {"x": 67.4, "y": 52.5}, "c22": {"x": 22.5, "y": 57.4},
    "c23": {"x": 42.3, "y": 57.8}, "c24": {"x": 55.9, "y": 62.4},
    "c25": {"x": 32.5, "y": 65.5}, "c26": {"x": 13.2, "y": 67.8},
    "c27": {"x": 22.5, "y": 69.3}, "c28": {"x": 46.8, "y": 71.5},
    "c29": {"x": 66.2, "y": 67.8}, "c30": {"x": 24.9, "y": 79.5},
    "c31": {"x": 36.7, "y": 79.7}, "c32": {"x": 46.7, "y": 85.8},
    "c33": {"x": 57.8, "y": 78.4, "station": True}, "c34": {"x": 70.0, "y": 82.4},
    "c35": {"x": 65.2, "y": 93.4}, "c36": {"x": 54.8, "y": 96.0},
}

# Every printed A–D marker is a distinct building location. The coordinates
# place components on the printed marker; the crossing remains authoritative
# for Bus passenger and route rules. A=1, B=2, C=3, D=4.
BUILDING_SITES = {
    "building_a_01": {"zone": 1, "crossing": "c12", "x": 26.5, "y": 38.4},
    "building_a_02": {"zone": 1, "crossing": "c13", "x": 40.8, "y": 31.4},
    "building_a_03": {"zone": 1, "crossing": "c15", "x": 36.2, "y": 39.3},
    "building_a_04": {"zone": 1, "crossing": "c15", "x": 42.5, "y": 38.4},
    "building_a_05": {"zone": 1, "crossing": "c16", "x": 52.1, "y": 40.9},
    "building_a_06": {"zone": 1, "crossing": "c16", "x": 45.6, "y": 47.5},
    "building_a_07": {"zone": 1, "crossing": "c19", "x": 36.2, "y": 49.8},
    "building_a_08": {"zone": 1, "crossing": "c19", "x": 34.4, "y": 56.6},
    "building_a_09": {"zone": 1, "crossing": "c23", "x": 46.3, "y": 57.8},
    "building_a_10": {"zone": 1, "crossing": "c23", "x": 41.4, "y": 62.7},
    "building_a_11": {"zone": 1, "crossing": "c24", "x": 52.5, "y": 61.3},
    "building_a_12": {"zone": 1, "crossing": "c28", "x": 42.9, "y": 69.1},
    "building_b_01": {"zone": 2, "crossing": "c1", "x": 13.2, "y": 5.2},
    "building_b_02": {"zone": 2, "crossing": "c10", "x": 59.5, "y": 25.5},
    "building_b_03": {"zone": 2, "crossing": "c8", "x": 64.2, "y": 24.5},
    "building_b_04": {"zone": 2, "crossing": "c11", "x": 13.4, "y": 36.5},
    "building_b_05": {"zone": 2, "crossing": "c13", "x": 51.0, "y": 33.3},
    "building_b_06": {"zone": 2, "crossing": "c17", "x": 24.6, "y": 49.8},
    "building_b_07": {"zone": 2, "crossing": "c22", "x": 25.0, "y": 54.2},
    "building_b_08": {"zone": 2, "crossing": "c25", "x": 30.0, "y": 59.7},
    "building_b_09": {"zone": 2, "crossing": "c20", "x": 55.6, "y": 52.9},
    "building_b_10": {"zone": 2, "crossing": "c29", "x": 63.9, "y": 63.5},
    "building_b_11": {"zone": 2, "crossing": "c31", "x": 36.7, "y": 83.9},
    "building_b_12": {"zone": 2, "crossing": "c35", "x": 68.1, "y": 93.0},
    "building_c_01": {"zone": 3, "crossing": "c9", "x": 33.9, "y": 20.9},
    "building_c_02": {"zone": 3, "crossing": "c11", "x": 13.2, "y": 31.8},
    "building_c_03": {"zone": 3, "crossing": "c12", "x": 25.4, "y": 31.5},
    "building_c_04": {"zone": 3, "crossing": "c13", "x": 44.8, "y": 27.2},
    "building_c_05": {"zone": 3, "crossing": "c17", "x": 19.6, "y": 51.7},
    "building_c_06": {"zone": 3, "crossing": "c20", "x": 58.6, "y": 46.6},
    "building_c_07": {"zone": 3, "crossing": "c24", "x": 58.6, "y": 67.5},
    "building_c_08": {"zone": 3, "crossing": "c29", "x": 69.1, "y": 68.6},
    "building_c_09": {"zone": 3, "crossing": "c28", "x": 47.0, "y": 76.2},
    "building_d_01": {"zone": 4, "crossing": "c2", "x": 30.7, "y": 4.7},
    "building_d_02": {"zone": 4, "crossing": "c5", "x": 35.2, "y": 7.5},
    "building_d_03": {"zone": 4, "crossing": "c6", "x": 46.7, "y": 12.0},
    "building_d_04": {"zone": 4, "crossing": "c7", "x": 58.4, "y": 6.7},
    "building_d_05": {"zone": 4, "crossing": "c3", "x": 9.3, "y": 20.8},
    "building_d_06": {"zone": 4, "crossing": "c14", "x": 65.1, "y": 38.6},
    "building_d_07": {"zone": 4, "crossing": "c18", "x": 9.4, "y": 50.7},
    "building_d_08": {"zone": 4, "crossing": "c26", "x": 15.9, "y": 64.4},
    "building_d_09": {"zone": 4, "crossing": "c27", "x": 20.2, "y": 64.4},
    "building_d_10": {"zone": 4, "crossing": "c30", "x": 24.9, "y": 83.8},
    "building_d_11": {"zone": 4, "crossing": "c32", "x": 44.4, "y": 89.5},
    "building_d_12": {"zone": 4, "crossing": "c36", "x": 57.7, "y": 95.5},
    "building_d_13": {"zone": 4, "crossing": "c34", "x": 70.8, "y": 85.4},
}
EDGES = {
    "e1": ("c1", "c2"), "e3": ("c3", "c4"),
    "e4": ("c4", "c5"), "e5": ("c5", "c6"),
    "e7": ("c1", "c4"),
    "e10": ("c1", "c3"), "e11": ("c3", "c11"),
    "e13": ("c4", "c9"), "e14": ("c4", "c12"),
    "e16": ("c5", "c9"), "e17": ("c5", "c6"), "e18": ("c6", "c7"),
    "e20": ("c7", "c8"), "e21": ("c7", "c10"),
    "e23": ("c8", "c14"), "e24": ("c9", "c12"),
    "e25": ("c9", "c13"), "e26": ("c9", "c15"), "e27": ("c10", "c13"),
    "e28": ("c10", "c14"), "e29": ("c11", "c12"), "e30": ("c11", "c17"),
    "e31": ("c11", "c18"), "e32": ("c12", "c19"),
    "e34": ("c13", "c16"), "e35": ("c14", "c16"),
    "e37": ("c14", "c21"), "e38": ("c15", "c16"), "e39": ("c15", "c19"),
    "e40": ("c16", "c20"), "e41": ("c16", "c24"), "e42": ("c17", "c18"),
    "e43": ("c17", "c19"), "e44": ("c17", "c22"), "e45": ("c18", "c22"),
    "e46": ("c18", "c26"), "e48": ("c19", "c23"),
    "e49": ("c19", "c25"), "e50": ("c20", "c21"),
    "e52": ("c21", "c29"), "e53": ("c22", "c25"), "e54": ("c22", "c27"),
    "e55": ("c23", "c25"), "e56": ("c23", "c28"), "e57": ("c24", "c28"),
    "e58": ("c24", "c29"), "e59": ("c24", "c33"),
    "e61": ("c25", "c31"), "e62": ("c26", "c27"), "e63": ("c26", "c30"),
    "e64": ("c27", "c30"), "e65": ("c28", "c31"), "e66": ("c28", "c32"),
    "e67": ("c29", "c33"), "e68": ("c29", "c34"), "e69": ("c30", "c31"),
    "e71": ("c31", "c32"), "e72": ("c32", "c33"),
    "e73": ("c32", "c36"), "e75": ("c33", "c35"),
    "e76": ("c34", "c35"),
    "e78": ("c2", "c4"), "e79": ("c4", "c11"), "e80": ("c9", "c6"),
    "e81": ("c13", "c6"), "e82": ("c23", "c16"), "e83": ("c25", "c30"),
    "e84": ("c28", "c33"), "e85": ("c33", "c36"), "e86": ("c33", "c34"),
    "e87": ("c20", "c24"), "e88": ("c24", "c21"),
}
STATION_CROSSINGS = tuple(node_id for node_id, node in NODES.items() if node.get("station"))
# The four crossings bordering the central park block on the supplied board.
# Initial passengers occupy one each; later Passengers actions use stations.
CENTRAL_PARK_CROSSINGS = ("c15", "c16", "c19", "c23")


def _player_ids(state: dict[str, Any]) -> list[str]:
    return [player["player_id"] for player in state.get("players", [])]


def _next_player(player_ids: list[str], current: str) -> str:
    return player_ids[(player_ids.index(current) + 1) % len(player_ids)]


def _selection_slot(action_spaces: dict[str, list[str]], action_type: str) -> str:
    return chr(ord("A") + len(action_spaces[action_type]))


def _building_instance(site_id: str, building_type: str, owner_id: str | None = None) -> dict[str, Any]:
    """Create the authoritative instance stored at a unique building location."""
    return {
        "building_id": f"building-{site_id}",
        "type": building_type,
        "owner_id": owner_id,
        "occupied_by": None,
    }


class BusValidator(LegalMoveValidator):
    """Validator-owned implementation for Bus setup and action drafting."""

    def initial_game_data(
        self, rng_seed: int = 42, player_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        player_ids = player_ids or ["player_1", "player_2", "player_3"]
        stones = 4 if len(player_ids) == 3 else 5
        starting_player = create_rng(rng_seed).choice(player_ids)
        return {
            "rules_edition": "standard_2019",
            "current_phase": "SETUP_BUILDINGS",
            "current_player": starting_player,
            "round_number": 0,
            "starting_player": starting_player,
            "setup": {"building_placements": {pid: 0 for pid in player_ids},
                      "first_route_placed": [], "second_route_placed": []},
            "players": {pid: {"action_markers": 20, "buses": 1,
                               "time_stones": 0, "score": 0,
                               "score_stack_order": index,
                               "route_anchor": None,
                               "route_edges": []} for index, pid in enumerate(player_ids)},
            "buildings": {},
            "building_tiles_remaining": {kind: BUILDING_TILES_PER_TYPE for kind in BUILDING_TYPES},
            "action_spaces": {action: [] for action in ACTION_TYPES},
            "passed_this_round": [],
            "resolution": None,
            "clock": "house",
            "time_stones_remaining": stones,
            "passenger_supply": 11,
            "passengers": {
                f"central_park_{index}": crossing
                for index, crossing in enumerate(CENTRAL_PARK_CROSSINGS, start=1)
            },
            "terminal_reason": None,
            "next_starting_player": None,
            "game_over": False,
        }

    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        data = state.get("game_data", {})
        if data.get("game_over") or data.get("current_player") != player_id:
            return []
        phase = data.get("current_phase")
        if phase == "SETUP_BUILDINGS":
            return self._setup_building_moves(data, player_id)
        if phase in {"SETUP_FIRST_ROUTE_SEGMENTS", "SETUP_SECOND_ROUTE_SEGMENTS"}:
            return self._route_moves(data, player_id)
        if phase == "ACTION_SELECTION":
            return self._selection_moves(data, player_id)
        if phase.startswith("RESOLVE_"):
            return self._resolution_moves(data, player_id)
        return []

    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        player_id = move.get("player_id")
        return any(
            candidate.get("move_id") == move.get("move_id") and candidate == move
            for candidate in self.get_legal_moves(state, player_id)
        )

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(state)
        data = result["game_data"]
        move_type = move["type"]
        if move_type == "setup_building":
            self._apply_setup_building(data, move)
        elif move_type in {"setup_first_route", "setup_second_route"}:
            self._apply_route(data, move)
        elif move_type == "select_action":
            self._apply_action_selection(data, move, _player_ids(result))
        elif move_type == "pass_action_selection":
            self._apply_pass(data, move, _player_ids(result))
        else:
            self._apply_resolution_move(data, move, _player_ids(result))
        return {"game_data": data}

    def check_win(self, state: dict[str, Any]) -> str | None:
        data = state.get("game_data", {})
        if not data.get("game_over"):
            return None
        ranked = sorted(
            data["players"],
            key=lambda pid: (data["players"][pid]["score"] - data["players"][pid]["time_stones"],
                             data["players"][pid]["time_stones"],
                             -data["players"][pid]["score_stack_order"]),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def recommend_ai_move(self, state: dict[str, Any], candidate_moves: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Lightweight bot for exercising the full game loop.

        During ACTION_SELECTION, picks a random legal action slot (instead of
        always the first `ACTION_TYPES` entry, i.e. line_expansion) so the bot
        exercises passengers/buildings/clock/vrrooomm too, and voluntarily
        passes once it has selected three actions this round so the
        Resolve Actions phase gets exercised before a player exhausts all
        markers. Resolution-phase choices (which card to play, which site to
        build, etc.) are also randomized among the legal options.
        """
        import random

        if not candidate_moves:
            return None
        # Smarter opening: use the rule policy's setup heuristics instead of
        # pure randomness for initial placement decisions.
        phase = state.get("game_data", {}).get("current_phase")
        if phase == "SETUP_BUILDINGS":
            preferred = sorted(candidate_moves, key=lambda m: (m.get("building_type") != "house", m.get("site_id", "")))
            return preferred[0] if preferred else None
        if phase in ("SETUP_FIRST_ROUTE_SEGMENTS", "SETUP_SECOND_ROUTE_SEGMENTS"):
            def touches_zone1(m):
                try:
                    from app.games.bus.rl_policies import _edge_touches_unbuilt_zone1_site
                    return 0 if _edge_touches_unbuilt_zone1_site(m["edge_id"]) else 1
                except Exception:
                    return 1
            ranked = sorted(candidate_moves, key=lambda m: (touches_zone1(m), m.get("edge_id", "")))
            return ranked[0] if ranked else None
        select_moves = [move for move in candidate_moves if move["type"] == "select_action"]
        pass_moves = [move for move in candidate_moves if move["type"] == "pass_action_selection"]
        if select_moves or pass_moves:
            player_id = (select_moves[0] if select_moves else pass_moves[0])["player_id"]
            data = state.get("game_data", {})
            selections = sum(
                pid == player_id
                for slots in data.get("action_spaces", {}).values()
                for pid in slots
            )
            if selections >= 3 and pass_moves:
                return pass_moves[0]
            if select_moves:
                return random.choice(select_moves)
            return pass_moves[0]
        return random.choice(candidate_moves)

    def serialize_for_screen(self, game_data: dict[str, Any]) -> dict[str, Any]:
        from app.games.bus.serialize import serialize_game_data
        return serialize_game_data(
            game_data,
            nodes=NODES,
            building_sites=BUILDING_SITES,
            edges=EDGES,
            route_ends={
                player_id: sorted(self._route_endpoints(player))
                for player_id, player in game_data["players"].items()
            },
        )

    def _setup_building_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        occupied = set(data["buildings"])
        tiles = data.get("building_tiles_remaining", {})
        return [{"move_id": f"setup-building-{site_id}-{kind}", "type": "setup_building",
                 "player_id": player_id, "site_id": site_id, "building_type": kind}
                for site_id, site in BUILDING_SITES.items() if site["zone"] == 1 and site_id not in occupied
            for kind in BUILDING_TYPES if tiles.get(kind, BUILDING_TILES_PER_TYPE) > 0]

    def _route_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        own_edges = data["players"][player_id]["route_edges"]
        phase = data["current_phase"]
        if phase == "SETUP_FIRST_ROUTE_SEGMENTS":
            return [{"move_id": f"setup_first_route-{edge_id}", "type": "setup_first_route",
                     "player_id": player_id, "edge_id": edge_id} for edge_id in EDGES]
        return self._route_extensions(data, player_id, "setup_second_route")

    def _selection_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        player = data["players"][player_id]
        if player_id in data["passed_this_round"] or player["action_markers"] == 0:
            return []
        moves = []
        for action in ACTION_TYPES:
            taken = data["action_spaces"][action]
            if len(taken) >= ACTION_SLOT_LIMITS[action]:
                continue
            if action == "buses" and player["buses"] >= 5:
                continue
            moves.append({"move_id": f"select-{action}-{_selection_slot(data['action_spaces'], action)}",
                          "type": "select_action", "player_id": player_id,
                          "action_type": action, "slot": _selection_slot(data["action_spaces"], action)})
        selections = sum(pid == player_id for slots in data["action_spaces"].values() for pid in slots)
        if selections >= 2:
            moves.append({"move_id": "pass-action-selection", "type": "pass_action_selection", "player_id": player_id})
        return moves

    def _resolution_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        resolution = data.get("resolution")
        if not resolution or resolution["player_id"] != player_id:
            return []
        action = resolution["action_type"]
        if resolution.get("remaining", 0) <= 0:
            return [{"move_id": f"complete-{action}", "type": "complete_resolution", "player_id": player_id}]
        if action == "line_expansion":
            moves = self._line_expansion_moves(data, player_id)
        elif action == "buses":
            moves = ([{"move_id": "buy-bus", "type": "buy_bus", "player_id": player_id}]
                     if data["players"][player_id]["buses"] < 5 else [])
        elif action == "passengers":
            moves = ([{"move_id": f"place-passenger-{station}", "type": "place_passenger",
                       "player_id": player_id, "station": station}
                      for station in STATION_CROSSINGS]
                     if data["passenger_supply"] > 0 else [])
        elif action == "buildings":
            moves = self._building_moves(data, player_id)
        elif action == "clock":
            moves = [
                {"move_id": "clock-stop", "type": "clock_stop", "player_id": player_id},
                {"move_id": "clock-advance", "type": "clock_advance", "player_id": player_id},
            ] if data["time_stones_remaining"] else [{"move_id": "clock-advance", "type": "clock_advance", "player_id": player_id}]
        elif action == "vrrooomm":
            moves = self._transport_moves(data, player_id)
        else:
            moves = []
        if not moves:
            return [{"move_id": f"complete-{action}", "type": "complete_resolution", "player_id": player_id}]
        return moves

    def _line_expansion_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        return self._route_extensions(data, player_id, "line_expand")

    def _route_extensions(self, data: dict[str, Any], player_id: str, move_type: str) -> list[dict[str, Any]]:
        """Return legal endpoint extensions under the core shared-street rule.

        A route may only grow from an end.  It must prefer an unoccupied
        outgoing street; parallel use of an opponent street is allowed only
        when no empty street remains at that selected end.
        """
        own = data["players"][player_id]["route_edges"]
        if len(own) >= MAX_LINE_MARKERS_PER_PLAYER:
            return []
        endpoints = self._route_endpoints(data["players"][player_id])
        candidates: list[tuple[str, str, bool]] = []
        occupied_by_other = {
            edge_id for pid, player in data["players"].items() if pid != player_id
            for edge_id in player["route_edges"]
        }
        for endpoint in endpoints:
            outgoing = [(edge_id, edge_ends) for edge_id, edge_ends in EDGES.items()
                        if endpoint in edge_ends and edge_id not in own]
            has_empty = any(edge_id not in occupied_by_other for edge_id, _ in outgoing)
            for edge_id, _ in outgoing:
                parallel_owners = [
                    player for pid, player in data["players"].items()
                    if pid != player_id and edge_id in player["route_edges"]
                ]
                # A shared-end exception can accompany every existing line on
                # the street only when every such route also ends here.  This
                # is particularly important when attempting to add a third
                # line to an already shared street.
                shared_end_exception = bool(parallel_owners) and all(
                    endpoint in self._route_endpoints(player)
                    for player in parallel_owners
                )
                if not has_empty or edge_id not in occupied_by_other or shared_end_exception:
                    candidates.append((edge_id, endpoint, edge_id in occupied_by_other))
        return [{"move_id": f"{move_type}-{edge_id}-from-{endpoint}", "type": move_type,
                 "player_id": player_id, "edge_id": edge_id,
                 "from_crossing": endpoint, "parallel": parallel}
                for edge_id, endpoint, parallel in candidates]

    def _route_endpoints(self, player: dict[str, Any]) -> set[str]:
        degrees: dict[str, int] = {}
        for edge_id in player["route_edges"]:
            for crossing in EDGES[edge_id]:
                degrees[crossing] = degrees.get(crossing, 0) + 1
        # A valid route is an Euler trail: ordinary ends have degree one; a
        # loop extended from its closure has degrees three and one.  Both odd
        # vertices remain legal expansion ends in that latter situation.
        endpoints = {crossing for crossing, degree in degrees.items() if degree % 2 == 1}
        if endpoints:
            return endpoints
        return {player["route_anchor"]} if player.get("route_anchor") else set()

    def _building_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        occupied = set(data["buildings"])
        tiles = data.get("building_tiles_remaining", {})
        current_zone = min((site["zone"] for site_id, site in BUILDING_SITES.items() if site_id not in occupied), default=None)
        if current_zone is None:
            return []
        return [{"move_id": f"build-{site_id}-{kind}", "type": "build",
                 "player_id": player_id, "site_id": site_id, "building_type": kind}
                for site_id, site in BUILDING_SITES.items()
                if site["zone"] == current_zone and site_id not in occupied
                for kind in BUILDING_TYPES if tiles.get(kind, BUILDING_TILES_PER_TYPE) > 0]

    def _transport_moves(self, data: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        crossings = {node for edge_id in data["players"][player_id]["route_edges"] for node in EDGES[edge_id]}
        destinations = [site_id for site_id, building in data["buildings"].items()
                        if building["type"] == data["clock"] and building["occupied_by"] is None
                        and BUILDING_SITES[site_id]["crossing"] in crossings]
        moves = []
        for passenger_id, location in data["passengers"].items():
            source_crossing = BUILDING_SITES[location.removeprefix("building:")]["crossing"] if location.startswith("building:") else location
            if source_crossing not in crossings:
                continue
            if location.startswith("building:") and data["buildings"][location.removeprefix("building:")]["type"] == data["clock"]:
                continue
            for site_id in destinations:
                moves.append({"move_id": f"transport-{passenger_id}-{site_id}", "type": "transport",
                              "player_id": player_id, "passenger_id": passenger_id, "destination_site": site_id})
        return moves

    def _apply_setup_building(self, data: dict[str, Any], move: dict[str, Any]) -> None:
        pid = move["player_id"]
        data["buildings"][move["site_id"]] = _building_instance(
            move["site_id"], move["building_type"], pid,
        )
        data["building_tiles_remaining"][move["building_type"]] -= 1
        self._settle_passengers(data)
        placed = data["setup"]["building_placements"]
        placed[pid] += 1
        player_ids = list(data["players"])
        if all(count == 2 for count in placed.values()):
            data["current_phase"] = "SETUP_FIRST_ROUTE_SEGMENTS"
            data["current_player"] = data["starting_player"]
        else:
            data["current_player"] = _next_player(player_ids, pid)

    def _apply_route(self, data: dict[str, Any], move: dict[str, Any]) -> None:
        pid, phase = move["player_id"], data["current_phase"]
        data["players"][pid]["route_edges"].append(move["edge_id"])
        self._refresh_route_anchor(data["players"][pid], move.get("from_crossing"))
        player_ids = list(data["players"])
        if phase == "SETUP_FIRST_ROUTE_SEGMENTS":
            data["setup"]["first_route_placed"].append(pid)
            if len(data["setup"]["first_route_placed"]) == len(player_ids):
                data["current_phase"] = "SETUP_SECOND_ROUTE_SEGMENTS"
                start_index = player_ids.index(data["starting_player"])
                data["current_player"] = player_ids[(start_index - 1) % len(player_ids)]
            else:
                data["current_player"] = _next_player(player_ids, pid)
            return
        data["setup"]["second_route_placed"].append(pid)
        if len(data["setup"]["second_route_placed"]) == len(player_ids):
            data["current_phase"] = "ACTION_SELECTION"
            data["round_number"] = 1
            data["current_player"] = data["starting_player"]
        else:
            data["current_player"] = player_ids[(player_ids.index(pid) - 1) % len(player_ids)]

    def _apply_action_selection(self, data: dict[str, Any], move: dict[str, Any], player_ids: list[str]) -> None:
        pid, action = move["player_id"], move["action_type"]
        data["action_spaces"][action].append(pid)
        data["players"][pid]["action_markers"] -= 1
        self._advance_selection_actor(data, player_ids, pid)

    def _apply_pass(self, data: dict[str, Any], move: dict[str, Any], player_ids: list[str]) -> None:
        pid = move["player_id"]
        data["passed_this_round"].append(pid)
        self._advance_selection_actor(data, player_ids, pid)

    def _advance_selection_actor(self, data: dict[str, Any], player_ids: list[str], previous: str) -> None:
        eligible = [pid for pid in player_ids if pid not in data["passed_this_round"] and data["players"][pid]["action_markers"]]
        if not eligible:
            self._begin_next_resolution(data, player_ids)
            return
        for offset in range(1, len(player_ids) + 1):
            candidate = player_ids[(player_ids.index(previous) + offset) % len(player_ids)]
            if candidate in eligible:
                data["current_player"] = candidate
                return

    def _begin_next_resolution(self, data: dict[str, Any], player_ids: list[str]) -> None:
        """Advance to the next selected action-marker resolution."""
        previous = data.get("resolution")
        start_action = ACTION_TYPES.index(previous["action_type"]) if previous else 0
        start_resolution_index = previous.get("resolution_index", previous["slot_index"]) + 1 if previous else 0
        for action_index in range(start_action, len(ACTION_TYPES)):
            action = ACTION_TYPES[action_index]
            owners = data["action_spaces"][action]
            if action == "clock" and not owners:
                data["clock"] = {"house": "office", "office": "pub", "pub": "house"}[data["clock"]]
                self._settle_passengers(data)
                continue
            ordered = (
                list(reversed(list(enumerate(owners))))
                if action in {"line_expansion", "buildings"}
                else list(enumerate(owners))
            )
            resolution_start = start_resolution_index if action_index == start_action else 0
            if resolution_start < len(ordered):
                resolution_index = resolution_start
                slot_index, player_id = ordered[resolution_index]
                quantity = self._action_quantity(data, action, slot_index, len(player_ids), player_id)
                data["resolution"] = {"action_type": action, "slot_index": slot_index,
                                      "resolution_index": resolution_index,
                                      "player_id": player_id, "remaining": quantity}
                data["current_phase"] = RESOLUTION_PHASES[action]
                data["current_player"] = player_id
                return
        self._complete_round(data, player_ids)

    def _action_quantity(
        self, data: dict[str, Any], action: str, slot_index: int, player_count: int,
        player_id: str,
    ) -> int:
        maximum_buses = max(player["buses"] for player in data["players"].values())
        if action == "line_expansion":
            return max(0, maximum_buses - slot_index + (1 if player_count == 5 else 0))
        if action in {"passengers", "buildings"}:
            return max(0, maximum_buses - slot_index)
        if action == "vrrooomm":
            return data["players"][player_id]["buses"]
        return 1

    def _apply_resolution_move(self, data: dict[str, Any], move: dict[str, Any], player_ids: list[str]) -> None:
        resolution = data["resolution"]
        action = resolution["action_type"]
        move_type = move["type"]
        if move_type == "line_expand":
            data["players"][move["player_id"]]["route_edges"].append(move["edge_id"])
            self._refresh_route_anchor(data["players"][move["player_id"]], move.get("from_crossing"))
        elif move_type == "buy_bus":
            data["players"][move["player_id"]]["buses"] += 1
        elif move_type == "place_passenger":
            passenger_id = f"passenger_{data['passenger_supply']}"
            data["passengers"][passenger_id] = move["station"]
            data["passenger_supply"] -= 1
            self._settle_passengers(data)
        elif move_type == "build":
            data["buildings"][move["site_id"]] = _building_instance(
                move["site_id"], move["building_type"], move["player_id"],
            )
            data["building_tiles_remaining"][move["building_type"]] -= 1
            self._settle_passengers(data)
        elif move_type == "clock_stop":
            data["players"][move["player_id"]]["time_stones"] += 1
            data["time_stones_remaining"] -= 1
            if data["time_stones_remaining"] == 0:
                data["game_over"] = True
                data["terminal_reason"] = "clock_rupture"
                data["current_phase"] = "GAME_OVER"
                data["current_player"] = None
                return
        elif move_type == "clock_advance":
            data["clock"] = {"house": "office", "office": "pub", "pub": "house"}[data["clock"]]
            self._settle_passengers(data)
        elif move_type == "transport":
            passenger_id, site_id = move["passenger_id"], move["destination_site"]
            old_location = data["passengers"][passenger_id]
            if old_location.startswith("building:"):
                data["buildings"][old_location.removeprefix("building:")]["occupied_by"] = None
            data["passengers"][passenger_id] = f"building:{site_id}"
            data["buildings"][site_id]["occupied_by"] = passenger_id
            data["players"][move["player_id"]]["score"] += 1
            data["players"][move["player_id"]]["score_stack_order"] = max(
                player["score_stack_order"] for player in data["players"].values()
            ) + 1
        elif action == "starting_player" and move_type == "complete_resolution":
            data["next_starting_player"] = move["player_id"]
        if move_type != "complete_resolution":
            resolution["remaining"] = max(0, resolution["remaining"] - 1)
        if resolution["remaining"] == 0 or move_type == "complete_resolution":
            self._begin_next_resolution(data, player_ids)

    def _settle_passengers(self, data: dict[str, Any]) -> None:
        """Move satisfied passengers between their crossing and its demanded building.

        A passenger only occupies a building when its type matches the clock.
        When the demanded type changes, occupants return to their crossing;
        passengers at a crossing then fill matching empty buildings there in a
        deterministic order. This keeps the public board state aligned with
        the rulebook's satisfied-passenger convention.
        """
        for passenger_id, location in list(data["passengers"].items()):
            if not location.startswith("building:"):
                continue
            site_id = location.removeprefix("building:")
            building = data["buildings"].get(site_id)
            if building and building["type"] == data["clock"]:
                building["occupied_by"] = passenger_id
                continue
            if building:
                building["occupied_by"] = None
            data["passengers"][passenger_id] = BUILDING_SITES[site_id]["crossing"]

        for passenger_id in sorted(data["passengers"]):
            crossing = data["passengers"][passenger_id]
            if crossing.startswith("building:"):
                continue
            destination = next(
                (
                    site_id for site_id, building in data["buildings"].items()
                    if building["type"] == data["clock"]
                    and building["occupied_by"] is None
                    and BUILDING_SITES[site_id]["crossing"] == crossing
                ),
                None,
            )
            if destination:
                data["passengers"][passenger_id] = f"building:{destination}"
                data["buildings"][destination]["occupied_by"] = passenger_id

    def _complete_round(self, data: dict[str, Any], player_ids: list[str]) -> None:
        remaining_players = [pid for pid, player in data["players"].items() if player["action_markers"] > 0]
        if len(remaining_players) <= 1:
            data["game_over"] = True
            data["terminal_reason"] = "action_markers_exhausted"
            data["current_phase"] = "GAME_OVER"
            data["current_player"] = None
            return
        if len(data["buildings"]) == len(BUILDING_SITES):
            data["game_over"] = True
            data["terminal_reason"] = "building_locations_exhausted"
            data["current_phase"] = "GAME_OVER"
            data["current_player"] = None
            return
        data["round_number"] += 1
        data["starting_player"] = data["next_starting_player"] or _next_player(player_ids, data["starting_player"])
        data["next_starting_player"] = None
        data["current_phase"] = "ACTION_SELECTION"
        data["action_spaces"] = {action: [] for action in ACTION_TYPES}
        data["passed_this_round"] = []
        data["resolution"] = None
        start_index = player_ids.index(data["starting_player"])
        data["current_player"] = next(
            (
                player_ids[(start_index + offset) % len(player_ids)]
                for offset in range(len(player_ids))
                if data["players"][player_ids[(start_index + offset) % len(player_ids)]]["action_markers"] > 0
            ),
            data["starting_player"],
        )

    def _refresh_route_anchor(self, player: dict[str, Any], closing_crossing: str | None) -> None:
        """Remember the mandated continuation point after closing a route loop."""
        player["route_anchor"] = closing_crossing if not self._route_endpoints(player) else None