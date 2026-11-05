"""Configurable regional control classification and Twilight Struggle scoring."""
from __future__ import annotations

import json
import re
from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
from pathlib import Path
from typing import Any

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.rules import controlled_by
from app.games.twilight_struggle.rules import check_victory_conditions

_API_ROOT = Path(__file__).resolve().parents[3]
_SCORING_PATH = _API_ROOT / "configs" / "twilight_struggle" / "twilight_struggle_scoring.json"
FACTIONS = ("us", "ussr")
SOUTHEAST_ASIA_COUNTRIES = (
    "Burma",
    "Laos/Cambodia",
    "Vietnam",
    "Malaysia",
    "Indonesia",
    "Philippines",
    "Thailand",
)
SCORING_CARD_REGIONS = {
    "asia scoring": "Asia",
    "europe scoring": "Europe",
    "middle east scoring": "Middle East",
    "central america scoring": "Central America",
    "africa scoring": "Africa",
    "south america scoring": "South America",
    "southeast asia scoring": "Southeast Asia",
}


_SCORING_CACHE: dict[str, dict[str, Any]] = {}


def load_scoring_config(path: str | Path = _SCORING_PATH) -> dict[str, Any]:
    """Return the scoring config, read once per path. Shared; treat as read-only."""
    key = str(path)
    cached = _SCORING_CACHE.get(key)
    if cached is not None:
        return cached
    with Path(path).open("r", encoding="utf-8") as source:
        config = json.load(source)
    if not isinstance(config, dict) or not isinstance(config.get("regions"), dict):
        raise ValueError(f"Invalid Twilight Struggle scoring config: {path}")
    _SCORING_CACHE[key] = config
    return config


def classify_region(
    region: str,
    influences: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
    special_spaces: set[str] | None = None,
    formosan_resolution: bool = False,
) -> dict[str, Any]:
    """Classify region presence/domination/control using its non-special countries.

    ``formosan_resolution`` treats US-controlled Taiwan as a Battleground (Asia only).
    """
    data = country_data or load_country_data()
    excluded = special_spaces or set()
    spaces = [
        country for country in data["countries"].values()
        if country["region"] == region and country["name"] not in excluded
    ]
    if not spaces:
        raise ValueError(f"No country spaces configured for scoring region {region!r}")
    controlled = {faction: [] for faction in FACTIONS}
    controllers: dict[str, str | None] = {}
    for country in spaces:
        name = country["name"]
        controller = controlled_by(influences.get(name, {}), country)
        controllers[name] = controller
        if controller:
            controlled[controller].append(name)
    effective_battleground = {
        country["name"]: bool(country["battleground"])
        or (
            formosan_resolution
            and region == "Asia"
            and country["name"] == "Taiwan"
            and controllers[country["name"]] == "us"
        )
        for country in spaces
    }
    battlegrounds = {faction: [] for faction in FACTIONS}
    for name, controller in controllers.items():
        if controller and effective_battleground[name]:
            battlegrounds[controller].append(name)

    total = {faction: len(controlled[faction]) for faction in FACTIONS}
    bg_total = {faction: len(battlegrounds[faction]) for faction in FACTIONS}
    present = {faction: total[faction] > 0 for faction in FACTIONS}
    has_bg = {faction: bg_total[faction] > 0 for faction in FACTIONS}
    domination = {}
    control = {}
    for faction, opponent in (("us", "ussr"), ("ussr", "us")):
        domination[faction] = (
            present[faction]
            and total[faction] > total[opponent]
            and bg_total[faction] > bg_total[opponent]
            and has_bg[faction]
            and any(
                not effective_battleground[country["name"]] and country["name"] in controlled[faction]
                for country in spaces
            )
        )
        control[faction] = (
            total[faction] > total[opponent]
            and bg_total[faction] == sum(effective_battleground.values())
        )
    return {
        "region": region,
        "countries": [country["name"] for country in spaces],
        "controlled_countries": controlled,
        "battlegrounds": battlegrounds,
        "country_count": total,
        "battleground_count": bg_total,
        "presence": present,
        "domination": domination,
        "control": control,
    }


def score_region(
    region: str,
    influences: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
    scoring_config: dict[str, Any] | None = None,
    formosan_resolution: bool = False,
    ussr_battleground_penalty: int = 0,
) -> dict[str, Any]:
    """Return score breakdown and US-relative VP for a major scoring region."""
    data = country_data or load_country_data()
    config = scoring_config or load_scoring_config()
    try:
        values = config["regions"][region]
    except KeyError as error:
        raise ValueError(f"No scoring values configured for {region!r}") from error
    state = classify_region(
        region,
        influences,
        data,
        set(config.get("special_spaces", []))
        | (set(SOUTHEAST_ASIA_COUNTRIES) if region == "Asia" else set()),
        formosan_resolution=formosan_resolution,
    )
    scores = {}
    for faction in FACTIONS:
        if state["control"][faction]:
            value = values["control"]
            battleground_bonus = values.get("battleground_domination_bonus", 1)
        elif state["domination"][faction]:
            value = values["domination"]
            battleground_bonus = values.get("battleground_domination_bonus", 1)
        elif state["presence"][faction]:
            value = values["presence"]
            battleground_bonus = values.get("battleground_presence_bonus", 1)
        else:
            value = 0
            battleground_bonus = values.get("battleground_presence_bonus", 1)
        battlegrounds_counted = state["battleground_count"][faction]
        if faction == "ussr":
            # Shuttle Diplomacy (73): subtract Battlegrounds from the USSR total for this scoring only.
            battlegrounds_counted = max(0, battlegrounds_counted - ussr_battleground_penalty)
        value += battlegrounds_counted * battleground_bonus
        enemy_superpower = "USSR" if faction == "us" else "United States"
        adjacent_to_enemy_superpower = {
            edge[0] if edge[1] == enemy_superpower else edge[1]
            for edge in data["superpower_adjacency"]
            if enemy_superpower in edge
        }
        value += sum(
            country in adjacent_to_enemy_superpower
            for country in state["controlled_countries"][faction]
        ) * values.get("enemy_superpower_adjacency_bonus", 0)
        scores[faction] = value
    return {**state, "score": scores, "vp_delta_us": scores["us"] - scores["ussr"]}


def calculate_major_region_final_score(
    current_vp_us_relative: int,
    influences: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
    scoring_config: dict[str, Any] | None = None,
    china_card_owner: str | None = None,
    formosan_resolution: bool = False,
) -> dict[str, Any]:
    """Aggregate the six major regions and Southeast Asian country points.

    The supplied rulebook also awards one final-scoring VP to the current China
    Card holder. Southeast Asian countries are excluded from Asia's Presence /
    Domination / Control classification and contribute their country points
    once here, equivalent to folding those points into final Asia scoring. Pass
    ``china_card_owner`` to include its point; without it the summary is
    explicitly incomplete.
    """
    data = country_data or load_country_data()
    config = scoring_config or load_scoring_config()
    regions = {
        name: score_region(name, influences, data, config, formosan_resolution=formosan_resolution)
        for name in config["regions"]
    }
    sea = score_southeast_asia(influences, data)
    region_delta = sum(result["vp_delta_us"] for result in regions.values()) + sea["vp_delta_us"]
    if china_card_owner not in {None, "us", "ussr"}:
        raise ValueError(f"Invalid China Card owner: {china_card_owner!r}")
    china_card_delta = 1 if china_card_owner == "us" else -1 if china_card_owner == "ussr" else 0
    final_vp = current_vp_us_relative + region_delta + china_card_delta
    # Europe Control is an automatic victory only when the Europe Scoring card is
    # played (see resolve_scoring_card). Final scoring is decided by VP alone.
    winner = "us" if final_vp > 0 else "ussr" if final_vp < 0 else "draw"
    reason = "final_scoring"
    return {
        "regions": regions,
        "southeast_asia": sea,
        "region_vp_delta_us": region_delta,
        "china_card_vp_delta_us": china_card_delta,
        "final_vp_us_relative": final_vp,
        "winner": winner,
        "reason": reason,
        "complete": china_card_owner is not None,
        "incomplete_reason": None if china_card_owner is not None else "China Card owner is required for final scoring.",
    }


def score_southeast_asia(
    influences: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score Southeast Asia by control of its seven card-listed countries."""
    data = country_data or load_country_data()
    scores = {"us": 0, "ussr": 0}
    controlled = {"us": [], "ussr": []}
    for name in SOUTHEAST_ASIA_COUNTRIES:
        if name not in data["countries"]:
            raise ValueError(f"Southeast Asia scoring country {name!r} missing from country data")
        controller = controlled_by(influences.get(name, {}), data["countries"][name])
        if controller:
            controlled[controller].append(name)
            scores[controller] += 2 if name == "Thailand" else 1
    return {
        "region": "Southeast Asia",
        "controlled_countries": controlled,
        "score": scores,
        "vp_delta_us": scores["us"] - scores["ussr"],
    }


def resolve_scoring_card(
    game_data: dict[str, Any],
    card: dict[str, Any],
    phasing_faction: str,
    country_data: dict[str, Any] | None = None,
    scoring_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a standard regional scoring card and check terminal conditions."""
    if not card.get("scoring"):
        raise ValueError("Card is not a scoring card")
    if phasing_faction not in FACTIONS:
        raise ValueError(f"Unknown phasing faction: {phasing_faction}")
    normalized_name = re.sub(r"[^a-z ]", "", card.get("name", "").casefold()).strip()
    region = SCORING_CARD_REGIONS.get(normalized_name)
    if region is None:
        raise ValueError(f"Unsupported scoring card: {card.get('name')!r}")
    updated = deepcopy(game_data)
    tracks = updated.get("tracks")
    if not isinstance(tracks, dict) or not isinstance(tracks.get("victory_points"), int):
        raise ValueError("game data must contain an integer victory_points track")
    influences = updated.get("countries")
    if not isinstance(influences, dict):
        raise ValueError("game data must contain country influence")
    data = country_data or load_country_data()
    shuttle = (updated.get("persistent_events") or {}).get("shuttle_diplomacy")
    shuttle_applies = isinstance(shuttle, dict) and region in {"Middle East", "Asia"}
    if region == "Southeast Asia":
        detail = score_southeast_asia(influences, data)
    else:
        detail = score_region(
            region,
            influences,
            data,
            scoring_config,
            formosan_resolution=bool((updated.get("persistent_events") or {}).get("formosan_resolution")),
            ussr_battleground_penalty=1 if shuttle_applies else 0,
        )
    tracks["victory_points"] += detail["vp_delta_us"]
    if shuttle_applies:
        updated["persistent_events"].pop("shuttle_diplomacy")
        updated.setdefault("discard_pile", []).append(shuttle["card"])
    europe_controller = None
    if region == "Europe":
        europe = detail if "control" in detail else classify_region("Europe", influences, data)
        europe_controller = next((f for f in FACTIONS if europe["control"][f]), None)
    terminal = check_victory_conditions(
        tracks["victory_points"],
        tracks.get("defcon", 5),
        phasing_faction,
        europe_control=europe_controller,
    )
    return {
        "game_data": updated,
        "region": region,
        "score_result": detail,
        "terminal_result": terminal,
    }
