"""Privacy-preserving Twilight Struggle view projection."""
from __future__ import annotations

from copy import deepcopy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.games.twilight_struggle.country_data import load_country_data

FACTIONS = {"us", "ussr"}


@lru_cache(maxsize=1)
def _map_positions() -> dict[str, dict[str, int]]:
    """Load accepted VASSAL map coordinates; adjacency remains a separate rules source."""
    draft_path = Path(__file__).resolve().parents[4] / "documentation" / "twilight-struggle" / "country-map-draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    return {
        item[0]: {"x": item[1], "y": item[2]}
        for item in draft.get("countries", [])
        if isinstance(item, list) and len(item) >= 3
        and isinstance(item[0], str) and isinstance(item[1], int) and isinstance(item[2], int)
    }


def serialize_game_state(game_data: dict[str, Any], viewer_faction: str | None) -> dict[str, Any]:
    """Return public state plus only the requested faction's private hand.

    The draw-pile order and unrevealed headline selections are never included.
    Invalid viewer values fail closed by omitting all hands and private data.
    """
    viewer = viewer_faction if viewer_faction in FACTIONS else None
    public = {
        key: deepcopy(value)
        for key, value in game_data.items()
        if key not in {
            "hands",
            "draw_pile",
            "headline_cards",
            "_rng_state_json",
            "rng_seed",
            "rng_state_json",
            "setup_config_source",
            "_event_hand_reveals",
            "revealed_hands",
            "_pending_event",
            "pending_event",
        }
    }
    public["hand"] = deepcopy(game_data.get("hands", {}).get(viewer, [])) if viewer else None
    public["hand_count"] = {
        faction: len(game_data.get("hands", {}).get(faction, []))
        for faction in sorted(FACTIONS)
    }
    public["draw_pile_count"] = len(game_data.get("draw_pile", []))
    public["map_positions"] = _map_positions()
    country_data = load_country_data()
    public["country_info"] = {
        name: {
            "region": info["region"],
            "stability": info["stability"],
            "battleground": info["battleground"],
            "adjacent_countries": country_data["adjacency"].get(name, []),
        }
        for name, info in country_data["countries"].items()
    }
    public["superpower_adjacency"] = country_data["superpower_adjacency"]
    public["headline_committed"] = {
        faction: game_data.get("headline_cards", {}).get(faction) is not None
        for faction in sorted(FACTIONS)
    }
    # Event-authorized knowledge is delivered only to the entitled opponent, never to observers.
    revealed = {}
    if viewer:
        turn = game_data.get("turn", 1)
        pending = game_data.get("_pending_event")
        if (
            viewer == "ussr" and isinstance(pending, dict)
            and pending.get("card", {}).get("id") == 98
            and game_data.get("current_phase") == "event_response"
        ):
            revealed["us"] = deepcopy(game_data.get("hands", {}).get("us", []))
        cia = (game_data.get("persistent_events") or {}).get("cia_created")
        if viewer == "us" and isinstance(cia, dict) and cia.get("expires_turn") == turn:
            revealed["ussr"] = deepcopy(game_data.get("hands", {}).get("ussr", []))
        snapshot = (game_data.get("_event_hand_reveals") or {}).get("lone_gunman")
        if (
            isinstance(snapshot, dict) and viewer == "ussr"
            and snapshot.get("viewer") == viewer and snapshot.get("faction") == "us"
            and snapshot.get("expires_turn") == turn
        ):
            revealed["us"] = deepcopy(snapshot.get("cards", []))
    if revealed:
        public["revealed_hands"] = revealed
    pending = game_data.get("_pending_event")
    if isinstance(pending, dict):
        public["pending_event"] = {
            "card_id": pending["card"]["id"], "sponsor": pending["sponsor"],
            "stage": game_data.get("current_phase"), "responding_player": game_data.get("current_player"),
        }
        if pending.get("our_man_tehran"):
            public["pending_event"]["choice_type"] = "private_revealed_card_subset"
        if pending.get("mode") == "operations":
                public["pending_event"]["mode"] = "operations"
                if "event_order" in pending:
                    public["pending_event"]["event_order"] = pending["event_order"]
    return public
