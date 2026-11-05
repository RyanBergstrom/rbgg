from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "fof" / "fields_of_fire_terrain.json"
_CSV_PATH = Path(__file__).resolve().parents[4] / "documentation" / "fof" / "terrain_cards.csv"


def _load_types() -> dict[str, dict[str, Any]]:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["terrain_types"]


TERRAIN_TYPES: dict[str, dict[str, Any]] = _load_types()


# Cache for CSV-loaded card data
_CARDS_CACHE: dict[str, dict[str, Any]] = {}
_CARDS_BY_DECK: dict[str, list[dict[str, Any]]] = {}


def _parse_bool(val: str | None) -> bool | None:
    if val is None or val.strip() == "":
        return None
    return val.strip().lower() in ("true", "1", "yes", "y")


def _parse_int(val: str | None) -> int | None:
    if val is None or val.strip() == "":
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


def _parse_borders(val: str | None) -> list[str] | None:
    if val is None or val.strip() == "":
        return None
    # Borders can be separated by | or comma
    if "|" in val:
        return [b.strip() for b in val.split("|")]
    elif "," in val:
        return [b.strip() for b in val.split(",")]
    else:
        return [b.strip() for b in val.split()]


def _load_cards() -> None:
    global _CARDS_CACHE, _CARDS_BY_DECK
    if _CARDS_CACHE:
        return
    
    _CARDS_CACHE = {}
    _CARDS_BY_DECK = {}
    
    with open(_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            card_id = (row.get("Card ID") or "").strip()
            if not card_id:
                continue
            
            deck = (row.get("Deck") or "").strip()
            terrain_type = (row.get("Terrain Type") or "").strip()
            terrain_name = (row.get("Terrain Name") or "").strip()
            file_name = (row.get("File Name") or row.get("\ufeffFile Name") or "").strip()
            
            # Build image path
            image = None
            if file_name:
                # The file_name is relative to documentation/fof/
                # Mount serves from documentation/fof/organized at /api/v1/img/fof/
                # Extract path relative to organized
                if file_name.startswith("organized/"):
                    image = f"/api/v1/img/fof/{file_name[len('organized/'): ]}"
                else:
                    image = f"/api/v1/img/fof/{file_name}"
            
            card_data = {
                "card_id": card_id,
                "deck": deck,
                "terrain_type": terrain_type,
                "terrain_name": terrain_name,
                "file_name": file_name,
                "image": image,
                "cover_high": _parse_int(row.get("Cover High")),
                "cover_low": _parse_int(row.get("Cover Low")),
                "burst": _parse_int(row.get("Burst")),
                "elevation": _parse_int(row.get("Elevation")),
                "landing_zone": _parse_bool(row.get("Landing Zone")),
                "trafficability": (row.get("Trafficability") or "").strip() or None,
                "cover_potential": _parse_int(row.get("Cover Potential")),
                "borders": _parse_borders(row.get("Borders")),
                "source": (row.get("Source") or "").strip() or None,
                "id_prefix": (row.get("ID Prefix") or "").strip() or None,
                "validated": (row.get("Validated") or "").strip(),
            }
            
            _CARDS_CACHE[card_id] = card_data
            if deck not in _CARDS_BY_DECK:
                _CARDS_BY_DECK[deck] = []
            _CARDS_BY_DECK[deck].append(card_data)


def get_card(card_id: str) -> dict[str, Any] | None:
    _load_cards()
    return _CARDS_CACHE.get(card_id)


def get_deck(deck_name: str) -> list[dict[str, Any]]:
    _load_cards()
    return _CARDS_BY_DECK.get(deck_name, [])


def list_decks() -> list[str]:
    _load_cards()
    return sorted(_CARDS_BY_DECK.keys())


def terrain_card(terrain_type: str, card_id: str | None = None) -> dict[str, Any]:
    _load_cards()
    
    # Start with type defaults
    info = TERRAIN_TYPES.get(terrain_type, {
        "name": terrain_type,
        "cover_high": 0,
        "cover_low": 0,
        "burst": 0,
        "elevation": 0,
        "landing_zone": False,
        "trafficability": "good",
        "cover_potential": 0,
        "borders": ["white", "white", "white", "white"],
        "source": None,
        "id_prefix": None,
        "image": None
    }).copy()
    
    result = {"card_id": card_id, "type": terrain_type, **info}
    
    # If we have a card_id, try to load card-specific data from CSV
    if card_id:
        card_data = get_card(card_id)
        if card_data:
            # Override with card-specific values if they exist
            if card_data["terrain_type"]:
                result["type"] = card_data["terrain_type"]
                # Re-merge type defaults for the actual terrain type
                type_info = TERRAIN_TYPES.get(card_data["terrain_type"], {}).copy()
                result.update({k: v for k, v in type_info.items() if k not in ["image"]})
            if card_data["terrain_name"]:
                result["name"] = card_data["terrain_name"]
            if card_data["image"]:
                result["image"] = card_data["image"]
            if card_data["cover_high"] is not None:
                result["cover_high"] = card_data["cover_high"]
            if card_data["cover_low"] is not None:
                result["cover_low"] = card_data["cover_low"]
            if card_data["burst"] is not None:
                result["burst"] = card_data["burst"]
            if card_data["elevation"] is not None:
                result["elevation"] = card_data["elevation"]
            if card_data["landing_zone"] is not None:
                result["landing_zone"] = card_data["landing_zone"]
            if card_data["trafficability"] is not None:
                result["trafficability"] = card_data["trafficability"]
            if card_data["cover_potential"] is not None:
                result["cover_potential"] = card_data["cover_potential"]
            if card_data["borders"] is not None:
                result["borders"] = card_data["borders"]
            if card_data["source"] is not None:
                result["source"] = card_data["source"]
            if card_data["id_prefix"] is not None:
                result["id_prefix"] = card_data["id_prefix"]
            if card_data["deck"]:
                result["deck"] = card_data["deck"]
    
    return result


def card_borders(card: dict[str, Any] | str) -> list[str]:
    if isinstance(card, str):
        card = terrain_card(card)
    borders = card.get("borders") or []
    # Ensure we have 4 borders
    while len(borders) < 4:
        borders.append("white")
    return borders[:4]


def border_dark(card: dict[str, Any] | str, side: int) -> bool:
    borders = card_borders(card)
    if side < 0 or side > 3:
        return False
    return borders[side].lower() == "dark"

