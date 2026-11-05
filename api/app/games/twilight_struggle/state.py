"""Initial Twilight Struggle board and track state from editable setup config."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.games.twilight_struggle.cards import standard_deck
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.turns import initialize_card_deal

_API_ROOT = Path(__file__).resolve().parents[3]
_SETUP_PATH = _API_ROOT / "configs" / "twilight_struggle" / "twilight_struggle_setup.json"


def load_setup_config(path: str | Path = _SETUP_PATH) -> dict[str, Any]:
    """Read setup values so corrections do not require changing rules code."""
    with Path(path).open("r", encoding="utf-8") as source:
        config = json.load(source)
    if not isinstance(config, dict) or not isinstance(config.get("starting_influence"), dict):
        raise ValueError(f"Invalid Twilight Struggle setup config: {path}")
    return config


def create_initial_game_data(
    rng_seed: int = 42,
    setup_path: str | Path = _SETUP_PATH,
) -> dict[str, Any]:
    """Create the configured board, player influence, and public game tracks.

    Starting influence, tracks, and the seeded opening deal are initialized.
    Event resolution and the action/turn validator remain incomplete, so this
    function must not be registered as a playable game on its own.
    """
    config = load_setup_config(setup_path)
    country_data = load_country_data()
    influence = {
        country["name"]: {"us": 0, "ussr": 0}
        for country in country_data["countries"].values()
        if country["name"] != "China"
    }
    for faction, placements in config["starting_influence"].items():
        if faction not in {"us", "ussr"}:
            raise ValueError(f"Unknown starting-influence faction: {faction}")
        for raw_country, amount in placements.items():
            country = raw_country
            if country not in influence:
                aliases = {"Dominican Republic": "Dominican Rep", "USA": "United States"}
                country = aliases.get(country, country)
            if country not in influence:
                raise ValueError(f"Unknown setup country: {raw_country}")
            if not isinstance(amount, int) or amount < 0:
                raise ValueError(f"Invalid setup influence for {raw_country}: {amount!r}")
            influence[country][faction] = amount

    totals = {
        faction: sum(country[faction] for country in influence.values())
        for faction in ("us", "ussr")
    }
    expected_totals = config.get("starting_influence_totals", {})
    if totals != expected_totals:
        raise ValueError(f"Starting influence totals {totals} do not match config {expected_totals}")

    tracks = config.get("initial_track_state", {})
    deal = initialize_card_deal(standard_deck(era=1), rng_seed)
    return {
        "rules_edition": "twilight_struggle_2nd_edition",
        "current_player": "player_2",
        "current_player_faction": "ussr",
        "player_by_faction": {"us": "player_1", "ussr": "player_2"},
        "faction_by_player": {"player_1": "us", "player_2": "ussr"},
        "current_phase": "headline",
        "ready_to_play": False,
        "blocker": "Complete card-event handlers and the turn/action validator before registration.",
        "rng_seed": deal["rng_seed"],
        "rng_state_json": deal["rng_state_json"],
        "countries": influence,
        "china_card": {"owner": tracks["china_card_owner"], "face_up": tracks["china_card_face_up"]},
        "tracks": {
            **tracks,
            "military_operations": dict(tracks["military_operations"]),
            "space_race": dict(tracks["space_race"]),
        },
        "turn": 1,
        "action_round": 0,
        "headline_cards": {"us": None, "ussr": None},
        "hands": deal["hands"],
        "draw_pile": deal["draw_pile"],
        "discard_pile": deal["discard_pile"],
        "removed_cards": deal["removed_cards"],
        "persistent_events": {},
        "setup_config_source": str(Path(setup_path)),
    }
