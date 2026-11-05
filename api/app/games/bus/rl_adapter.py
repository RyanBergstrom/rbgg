"""Dependency-free reference adapter for Bus reinforcement learning.

Mirrors the structure of ``app.games.lost_cities.rl_adapter``: this module has
no PettingZoo, Gymnasium, or ML dependency. It only exposes a fixed action-ID
contract, a fixed-size observation encoder, and a small in-memory reference
environment used to test the contract before any Gym wrapper or training code
exists. See ``documentation/Bus/bus-rl-analysis.md`` and
``documentation/Bus/bus-ppo-readiness.md`` for the design rationale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.rl_adapter import RLAdapter
from app.games.bus.validator import (
    ACTION_TYPES,
    BUILDING_SITES,
    BUILDING_TYPES,
    EDGES,
    STATION_CROSSINGS,
    BusValidator,
)

MAX_PLAYERS = 5
MAX_PASSENGER_SUPPLY = 11
CENTRAL_PARK_PASSENGER_COUNT = 4
MAX_ACTION_MARKERS = 20
MAX_LINE_MARKERS_PER_PLAYER = 25
MAX_BUSES = 6
MAX_TIME_STONES = 5
MAX_RESOLUTION_QUANTITY = 6

# Canonical, deterministic orderings. Every action ID and observation slot is
# derived from these tuples, never from the order moves happen to appear in a
# particular legal-move list.
SORTED_EDGE_IDS = tuple(sorted(EDGES, key=lambda edge_id: int(edge_id[1:])))
ALL_SITE_IDS = tuple(sorted(BUILDING_SITES))
ZONE1_SITE_IDS = tuple(
    sorted(site_id for site_id, site in BUILDING_SITES.items() if site["zone"] == 1)
)
# The fixed universe of passenger instance IDs the validator can ever create:
# the four fixed central-park passengers plus the numbered supply pool.
PASSENGER_ID_UNIVERSE = tuple(
    f"central_park_{index}" for index in range(1, CENTRAL_PARK_PASSENGER_COUNT + 1)
) + tuple(f"passenger_{index}" for index in range(1, MAX_PASSENGER_SUPPLY + 1))

PHASE_NAMES = (
    "SETUP_BUILDINGS",
    "SETUP_FIRST_ROUTE_SEGMENTS",
    "SETUP_SECOND_ROUTE_SEGMENTS",
    "ACTION_SELECTION",
    "RESOLVE_LINE_EXPANSION",
    "RESOLVE_BUSES",
    "RESOLVE_PASSENGERS",
    "RESOLVE_BUILDINGS",
    "RESOLVE_CLOCK",
    "RESOLVE_VRROOMM",
    "RESOLVE_STARTING_PLAYER",
    "GAME_OVER",
)

# --- Fixed action ID layout -------------------------------------------------
# Each family occupies a contiguous range. Ranges are computed from the
# canonical tuples above so the layout is reviewable and stable across runs.
_SELECT_ACTION_BASE = 0
_PASS_ACTION_SELECTION = len(ACTION_TYPES)
_SETUP_BUILDING_BASE = _PASS_ACTION_SELECTION + 1
# Route-growing moves are keyed by (edge, endpoint side) rather than just the
# edge, because the same not-yet-owned edge can be reachable from both of a
# player's current route endpoints (a near-closed loop); each side needs its
# own ID or two distinct legal moves would collide on one action ID.
_ROUTE_FAMILY_SIZE = len(SORTED_EDGE_IDS) * 2
_SETUP_FIRST_ROUTE_BASE = _SETUP_BUILDING_BASE + len(ZONE1_SITE_IDS) * len(BUILDING_TYPES)
_SETUP_SECOND_ROUTE_BASE = _SETUP_FIRST_ROUTE_BASE + _ROUTE_FAMILY_SIZE
_LINE_EXPAND_BASE = _SETUP_SECOND_ROUTE_BASE + _ROUTE_FAMILY_SIZE
_BUY_BUS = _LINE_EXPAND_BASE + _ROUTE_FAMILY_SIZE
_PLACE_PASSENGER_BASE = _BUY_BUS + 1
_BUILD_BASE = _PLACE_PASSENGER_BASE + len(STATION_CROSSINGS)
_CLOCK_STOP = _BUILD_BASE + len(ALL_SITE_IDS) * len(BUILDING_TYPES)
_CLOCK_ADVANCE = _CLOCK_STOP + 1
_TRANSPORT_BASE = _CLOCK_ADVANCE + 1
_COMPLETE_RESOLUTION = _TRANSPORT_BASE + len(PASSENGER_ID_UNIVERSE) * len(ALL_SITE_IDS)
ACTION_COUNT = _COMPLETE_RESOLUTION + 1


def action_id_for_move(move: dict[str, Any]) -> int:
    """Map one validator move to a stable fixed action ID.

    Raises ``ValueError`` for malformed or unsupported moves rather than
    silently creating an invalid mask.
    """
    move_type = move.get("type")
    if move_type == "select_action":
        action_type = move.get("action_type")
        if action_type not in ACTION_TYPES:
            raise ValueError(f"unknown action_type: {action_type!r}")
        return _SELECT_ACTION_BASE + ACTION_TYPES.index(action_type)
    if move_type == "pass_action_selection":
        return _PASS_ACTION_SELECTION
    if move_type == "setup_building":
        site_index = ZONE1_SITE_IDS.index(move["site_id"])
        type_index = BUILDING_TYPES.index(move["building_type"])
        return _SETUP_BUILDING_BASE + site_index * len(BUILDING_TYPES) + type_index
    if move_type in ("setup_first_route", "setup_second_route", "line_expand"):
        edge_id = move["edge_id"]
        edge_index = SORTED_EDGE_IDS.index(edge_id)
        from_crossing = move.get("from_crossing")
        endpoint_side = 0
        if from_crossing is not None:
            endpoint_side = EDGES[edge_id].index(from_crossing)
        offset = edge_index * 2 + endpoint_side
        if move_type == "setup_first_route":
            return _SETUP_FIRST_ROUTE_BASE + offset
        if move_type == "setup_second_route":
            return _SETUP_SECOND_ROUTE_BASE + offset
        return _LINE_EXPAND_BASE + offset
    if move_type == "buy_bus":
        return _BUY_BUS
    if move_type == "place_passenger":
        return _PLACE_PASSENGER_BASE + STATION_CROSSINGS.index(move["station"])
    if move_type == "build":
        site_index = ALL_SITE_IDS.index(move["site_id"])
        type_index = BUILDING_TYPES.index(move["building_type"])
        return _BUILD_BASE + site_index * len(BUILDING_TYPES) + type_index
    if move_type == "clock_stop":
        return _CLOCK_STOP
    if move_type == "clock_advance":
        return _CLOCK_ADVANCE
    if move_type == "transport":
        passenger_index = PASSENGER_ID_UNIVERSE.index(move["passenger_id"])
        site_index = ALL_SITE_IDS.index(move["destination_site"])
        return _TRANSPORT_BASE + passenger_index * len(ALL_SITE_IDS) + site_index
    if move_type == "complete_resolution":
        return _COMPLETE_RESOLUTION
    raise ValueError(f"unsupported Bus move: {move!r}")


def moves_by_action_id(legal_moves: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Build a fail-closed action map and reject duplicate action IDs."""
    mapped: dict[int, dict[str, Any]] = {}
    for move in legal_moves:
        action_id = action_id_for_move(move)
        if action_id in mapped:
            raise ValueError(f"multiple legal moves map to action {action_id}")
        mapped[action_id] = move
    return mapped


# --- Observation -------------------------------------------------------------
# Per-family feature counts documented here so OBSERVATION_SIZE stays
# reviewable without re-deriving it from the encoder body.
_GLOBAL_FEATURES = (
    len(PHASE_NAMES)      # phase one-hot
    + len(BUILDING_TYPES)  # clock one-hot
    + 1                   # time_stones_remaining / MAX_TIME_STONES
    + 1                   # passenger_supply / MAX_PASSENGER_SUPPLY
    + len(BUILDING_TYPES)  # building_tiles_remaining per type
    + 1                   # buildings placed / total sites
    + MAX_PLAYERS - 2     # player_count one-hot (3, 4, 5)
    + 1                   # current resolution remaining / MAX_RESOLUTION_QUANTITY
    + 1                   # game_over flag
)
_PLAYER_FEATURES = 1 + 1 + 1 + 1 + 1 + 1 + 1 + len(ACTION_TYPES) + 1
_EDGE_FEATURES = 4
_SITE_FEATURES_V1 = 3 + 4 + 1  # owner one-hot(empty/me/opponent) + zone one-hot + waiting passenger
_PASSENGER_FEATURES = 4
_STATION_FEATURES = 1

OBSERVATION_SCHEMA_VERSION = 2
OBSERVATION_SIZE_V1 = (
    _GLOBAL_FEATURES
    + MAX_PLAYERS * _PLAYER_FEATURES
    + len(SORTED_EDGE_IDS) * _EDGE_FEATURES
    + len(ALL_SITE_IDS) * _SITE_FEATURES_V1
    + len(PASSENGER_ID_UNIVERSE) * _PASSENGER_FEATURES
    + len(STATION_CROSSINGS) * _STATION_FEATURES
)
OBSERVATION_SIZE_V2 = OBSERVATION_SIZE_V1 + len(ALL_SITE_IDS) * len(BUILDING_TYPES)
OBSERVATION_SIZES = {1: OBSERVATION_SIZE_V1, 2: OBSERVATION_SIZE_V2}
OBSERVATION_SIZE = OBSERVATION_SIZE_V2


def _one_hot(index: int | None, size: int) -> list[float]:
    values = [0.0] * size
    if index is not None and 0 <= index < size:
        values[index] = 1.0
    return values


def _owner_relative(owner_id: str | None, player_id: str) -> int | None:
    if owner_id is None:
        return None
    return 0 if owner_id == player_id else 1


def _route_crossings(route_edges: list[str]) -> set[str]:
    crossings: set[str] = set()
    for edge_id in route_edges:
        crossings.update(EDGES[edge_id])
    return crossings


def _route_endpoints(route_edges: list[str]) -> set[str]:
    degrees: dict[str, int] = {}
    for edge_id in route_edges:
        for crossing in EDGES[edge_id]:
            degrees[crossing] = degrees.get(crossing, 0) + 1
    endpoints = {crossing for crossing, degree in degrees.items() if degree % 2 == 1}
    return endpoints


def encode_observation(
    state: dict[str, Any],
    player_id: str,
    legal_moves: list[dict[str, Any]] | None = None,
    version: int = OBSERVATION_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return a fixed-shape, player-relative observation for Bus.

    Bus is public information: every feature below is visible to every
    player, so there is no hidden-information leakage risk to guard against
    (unlike Lost Cities' hands/deck). The observer is always encoded first,
    followed by the remaining players in turn order; absent seats (fewer than
    ``MAX_PLAYERS`` players) are zero-padded.
    """
    if version not in OBSERVATION_SIZES:
        raise ValueError(f"unsupported observation version: {version}")
    data = state.get("game_data", {})
    player_ids = [player["player_id"] for player in state.get("players", [])]
    if player_id not in player_ids:
        raise ValueError(f"unknown player_id: {player_id!r}")
    start = player_ids.index(player_id)
    ordered_players = player_ids[start:] + player_ids[:start]

    values: list[float] = []

    # --- Globals ---
    values.extend(_one_hot(
        PHASE_NAMES.index(data.get("current_phase")) if data.get("current_phase") in PHASE_NAMES else None,
        len(PHASE_NAMES),
    ))
    values.extend(_one_hot(
        BUILDING_TYPES.index(data.get("clock")) if data.get("clock") in BUILDING_TYPES else None,
        len(BUILDING_TYPES),
    ))
    values.append(data.get("time_stones_remaining", 0) / MAX_TIME_STONES)
    values.append(data.get("passenger_supply", 0) / MAX_PASSENGER_SUPPLY)
    tiles = data.get("building_tiles_remaining", {})
    for kind in BUILDING_TYPES:
        values.append(tiles.get(kind, 0) / 30.0)
    values.append(len(data.get("buildings", {})) / len(BUILDING_SITES))
    values.extend(_one_hot(len(player_ids) - 3 if 3 <= len(player_ids) <= 5 else None, MAX_PLAYERS - 2))
    resolution = data.get("resolution")
    values.append((resolution.get("remaining", 0) if resolution else 0) / MAX_RESOLUTION_QUANTITY)
    values.append(1.0 if data.get("game_over") else 0.0)

    # --- Per-player (observer first, then turn order; padded to MAX_PLAYERS) ---
    players_data = data.get("players", {})
    action_spaces = data.get("action_spaces", {})
    passed = set(data.get("passed_this_round", []))
    for slot in range(MAX_PLAYERS):
        if slot < len(ordered_players):
            pid = ordered_players[slot]
            player = players_data.get(pid, {})
            route_edges = player.get("route_edges", [])
            values.append(1.0)
            values.append(player.get("action_markers", 0) / MAX_ACTION_MARKERS)
            values.append(player.get("buses", 0) / MAX_BUSES)
            values.append(player.get("time_stones", 0) / MAX_TIME_STONES)
            values.append((player.get("score", 0) - player.get("time_stones", 0)) / 20.0)
            values.append(len(route_edges) / MAX_LINE_MARKERS_PER_PLAYER)
            values.append(len(_route_endpoints(route_edges)) / 2.0)
            for action_type in ACTION_TYPES:
                owners = action_spaces.get(action_type, [])
                values.append(owners.count(pid) / ACTION_SLOT_LIMIT_FOR_NORMALIZATION)
            values.append(1.0 if pid in passed else 0.0)
        else:
            values.extend([0.0] * _PLAYER_FEATURES)

    # --- Edges (route network) ---
    my_player = players_data.get(player_id, {})
    my_endpoints = _route_endpoints(my_player.get("route_edges", []))
    for edge_id in SORTED_EDGE_IDS:
        owners = [pid for pid in player_ids if edge_id in players_data.get(pid, {}).get("route_edges", [])]
        is_mine = player_id in owners
        opponent_count = len(owners) - (1 if is_mine else 0)
        is_available = not owners
        crossings = EDGES[edge_id]
        is_candidate = bool(my_endpoints.intersection(crossings)) and not is_mine
        values.append(1.0 if is_mine else 0.0)
        values.append(opponent_count / max(1, MAX_PLAYERS - 1))
        values.append(1.0 if is_available else 0.0)
        values.append(1.0 if is_candidate else 0.0)

    # --- Building sites ---
    buildings = data.get("buildings", {})
    passengers = data.get("passengers", {})
    for site_id in ALL_SITE_IDS:
        building = buildings.get(site_id)
        relation = _owner_relative(building.get("owner_id") if building else None, player_id)
        values.extend(_one_hot(relation if building else None, 2))
        values.append(1.0 if building is None else 0.0)
        values.extend(_one_hot(BUILDING_SITES[site_id]["zone"] - 1, 4))
        has_waiting_passenger = any(
            location == f"building:{site_id}" for location in passengers.values()
        )
        values.append(1.0 if has_waiting_passenger else 0.0)
        if version >= 2:
            building_type = building.get("type") if building else None
            values.extend(_one_hot(
                BUILDING_TYPES.index(building_type) if building_type in BUILDING_TYPES else None,
                len(BUILDING_TYPES),
            ))

    # --- Passengers (fixed universe, padded by presence) ---
    my_crossings = _route_crossings(my_player.get("route_edges", []))
    for passenger_id in PASSENGER_ID_UNIVERSE:
        location = passengers.get(passenger_id)
        present = location is not None
        at_building = bool(present and location.startswith("building:"))
        clock_match = False
        source_crossing = None
        if present:
            if at_building:
                site = location.removeprefix("building:")
                building = buildings.get(site, {})
                clock_match = building.get("type") == data.get("clock")
                source_crossing = BUILDING_SITES.get(site, {}).get("crossing")
            else:
                source_crossing = location
        reachable = bool(present and source_crossing in my_crossings)
        values.append(1.0 if present else 0.0)
        values.append(1.0 if at_building else 0.0)
        values.append(1.0 if clock_match else 0.0)
        values.append(1.0 if reachable else 0.0)

    # --- Stations ---
    for crossing in STATION_CROSSINGS:
        waiting = sum(1 for location in passengers.values() if location == crossing)
        values.append(min(1.0, waiting / 4.0))

    legal = legal_moves if legal_moves is not None else []
    action_mask = [0] * ACTION_COUNT
    for action_id in moves_by_action_id(legal):
        action_mask[action_id] = 1
    return {"schema_version": version, "observation": values, "action_mask": action_mask}


ACTION_SLOT_LIMIT_FOR_NORMALIZATION = 6


@dataclass
class BusReferenceEnv(RLAdapter):
    """Small in-memory reference environment for adapter contract testing."""

    seed: int = 42
    player_ids: tuple[str, ...] = ("player_1", "player_2", "player_3")
    starting_player: str | None = None
    validator: BusValidator | None = None
    state: dict[str, Any] | None = None
    observation_version: int = OBSERVATION_SCHEMA_VERSION

    @property
    def action_count(self) -> int:
        return ACTION_COUNT

    @property
    def observation_size(self) -> int:
        return OBSERVATION_SIZES[self.observation_version]

    def __post_init__(self) -> None:
        if self.observation_version not in OBSERVATION_SIZES:
            raise ValueError(f"unsupported observation version: {self.observation_version}")
        if not 3 <= len(self.player_ids) <= 5:
            raise ValueError("Bus supports 3-5 players")
        self.validator = self.validator or BusValidator()

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            self.seed = seed
        game_data = self.validator.initial_game_data(
            rng_seed=self.seed, player_ids=list(self.player_ids),
        )
        if self.starting_player and self.starting_player in self.player_ids:
            game_data["starting_player"] = self.starting_player
            game_data["current_player"] = self.starting_player
        self.state = {
            "game_data": game_data,
            "players": [{"player_id": pid} for pid in self.player_ids],
        }
        return self.observe(self.current_player)

    @property
    def current_player(self) -> str:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        return self.state["game_data"]["current_player"]

    def legal_moves(self, player_id: str | None = None) -> list[dict[str, Any]]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        actor = player_id or self.current_player
        if actor is None:
            return []
        return self.validator.get_legal_moves(self.state, actor)

    def observe(
        self, player_id: str, legal_moves: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        legal = self.legal_moves(player_id) if legal_moves is None else legal_moves
        return encode_observation(self.state, player_id, legal, self.observation_version)

    def step(self, action_id: int) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        if self.state is None:
            raise RuntimeError("environment must be reset before use")
        if not isinstance(action_id, int) or not 0 <= action_id < ACTION_COUNT:
            raise ValueError(f"action must be an integer in [0, {ACTION_COUNT})")
        actor = self.current_player
        legal = self.legal_moves(actor)
        move = moves_by_action_id(legal).get(action_id)
        if move is None:
            raise ValueError(f"action {action_id} is illegal for {actor}")

        data = self.state["game_data"]
        before = data["players"][actor]["score"] - data["players"][actor]["time_stones"]
        result = self.validator.apply_move(self.state, move)
        self.state = {**self.state, **result, "game_data": result["game_data"]}

        done = bool(self.state["game_data"].get("game_over"))
        after_data = self.state["game_data"]
        after = after_data["players"][actor]["score"] - after_data["players"][actor]["time_stones"]
        reward = max(-1.0, min(1.0, (after - before) / 10.0))
        info: dict[str, Any] = {"actor": actor, "move": move}
        if done:
            ranking = self.validator.check_win(self.state)
            info["ranking"] = ranking
            # Alias for the shared ``app.core.rl_runner`` statistics collector,
            # which looks for "winner" regardless of game.
            info["winner"] = ranking
            info["final_scores"] = {
                pid: player["score"] - player["time_stones"]
                for pid, player in after_data["players"].items()
            }
        next_player = self.current_player
        next_legal = [] if done or next_player is None else self.legal_moves(next_player)
        return (
            self.observe(next_player, next_legal) if next_player else
            self.observe(actor, []),
            reward,
            done,
            info,
        )
