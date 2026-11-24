"""Generate initial cards.json catalog for Fields of Fire from api/img/fof/cards."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CARDS_DIR = PROJECT_ROOT / "api" / "img" / "fof" / "cards"
CONFIG_DIR = PROJECT_ROOT / "api" / "configs" / "fof"
CSV_PATH = PROJECT_ROOT / "documentation" / "fof" / "terrain_cards.csv"
TERRAIN_PRESETS_PATH = CONFIG_DIR / "fields_of_fire_terrain.json"


def load_csv_data() -> dict[str, dict]:
    results = {}
    if CSV_PATH.is_file():
        try:
            with CSV_PATH.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fn = row.get("File Name", "")
                    clean_fn = Path(fn).name
                    if clean_fn:
                        results[clean_fn] = row
        except Exception as e:
            print(f"Warning reading CSV: {e}")
    return results


def load_terrain_presets() -> dict[str, dict]:
    if TERRAIN_PRESETS_PATH.is_file():
        try:
            with TERRAIN_PRESETS_PATH.open("r", encoding="utf-8-sig") as f:
                data = json.load(f)
                return data.get("terrain_types", {})
        except Exception as e:
            print(f"Warning reading terrain presets: {e}")
    return {}


def classify_card(filename: str, csv_row: dict | None, presets: dict) -> dict:
    stem = Path(filename).stem
    lower = filename.lower()

    # Defaults
    card_type = "utility"
    deck = "Utility / Backs"
    expansion = "Base / Shared"
    purpose = "Rule Aid / Reference"
    name = stem
    terrain_details = None
    action_details = None

    # 1. Action Deck
    m_act = re.match(r"^0(\d{2})(f|b)?\.(png|jpg)$", filename, re.IGNORECASE)
    if m_act:
        card_type = "action"
        deck = "Action Deck"
        expansion = "Volume I"
        purpose = "Initiative, Combat Draw & Action Attempts"
        num = int(m_act.group(1))
        name = f"Action Card #{num}"
        action_details = {
            "card_number": num,
            "commands": None,
            "random_number": None,
            "attempt_icons": [],
            "hit_effects": None,
            "direction_arrow": None,
        }
    elif "action deck" in lower or "action" in lower and "back" in lower:
        card_type = "utility"
        deck = "Action Deck"
        expansion = "Volume I"
        purpose = "Card Back"
        name = "Action Deck Card Back"
    elif "reshuffle" in lower:
        card_type = "action"
        deck = "Action Deck"
        expansion = "Volume I"
        purpose = "Deck Reshuffle"
        name = "Reshuffle Card"
        action_details = {
            "card_number": None,
            "commands": None,
            "random_number": None,
            "attempt_icons": ["Reshuffle"],
            "hit_effects": None,
            "direction_arrow": None,
        }

    # 2. Fire Support Areas (FSA)
    elif "fire support area" in lower or "fsa" in lower:
        card_type = "fsa"
        deck = "Fire Support Areas"
        expansion = "Volume III"
        purpose = "Fire Support Base"
        name = stem

    # 3. Staging Areas
    elif "staging area" in lower:
        card_type = "staging_area"
        deck = "Staging Areas"
        expansion = "Volume III"
        purpose = "Off-map Staging"
        name = stem

    # 4. Card Backs
    elif "card back" in lower or "card - back" in lower or lower.endswith("back.png") or lower.endswith("back.jpg"):
        card_type = "utility"
        deck = "Card Backs / Aids"
        expansion = "Base / Shared"
        purpose = "Card Back"
        name = stem

    # 5. Rule Aids / Specials
    elif "keep up the fire" in lower:
        card_type = "utility"
        deck = "Card Backs / Aids"
        expansion = "Volume I"
        purpose = "Rule Aid / Reference"
        name = "Keep Up The Fire Reference Card"
    elif "plantation" in lower:
        card_type = "terrain"
        deck = "Vietnam Terrain"
        expansion = "Volume I"
        purpose = "Map Terrain Grid"
        name = stem
        terrain_details = {
            "terrain_name": "Rubber Plantation",
            "terrain_category": "Forest / Woods",
            "cover_high": 1,
            "cover_low": 1,
            "burst_modifier": 0,
            "elevation": 0,
            "landing_zone": "None",
            "trafficability": "fair",
            "cover_potential": 2,
            "borders": {"north": "white", "east": "white", "south": "white", "west": "white"},
            "features": ["Plantation"],
        }

    # 6. Specific Terrain Decks
    elif re.match(r"^N\d{2}", filename):
        card_type = "terrain"
        deck = "Normandy Terrain"
        expansion = "Volume I"
        purpose = "Map Terrain Grid"
        raw_name = filename[3:].rsplit(".", 1)[0].strip() or "Normandy Terrain"
        name = f"N{filename[1:3]} - {raw_name}"
        terrain_details = make_terrain_details(raw_name, presets)
    elif re.match(r"^K\d{2}", filename):
        card_type = "terrain"
        deck = "Korea Terrain"
        expansion = "Volume I"
        purpose = "Map Terrain Grid"
        raw_name = filename[3:].rsplit(".", 1)[0].strip() or "Korea Terrain"
        name = f"K{filename[1:3]} - {raw_name}"
        terrain_details = make_terrain_details(raw_name, presets)
    elif re.match(r"^V\d{2}", filename):
        card_type = "terrain"
        deck = "Vietnam Terrain"
        expansion = "Volume I"
        purpose = "Map Terrain Grid"
        raw_name = filename[3:].rsplit(".", 1)[0].strip() or "Vietnam Terrain"
        name = f"V{filename[1:3]} - {raw_name}"
        terrain_details = make_terrain_details(raw_name, presets)
    elif filename.startswith("HBR"):
        card_type = "terrain"
        deck = "Heartbreak Ridge Terrain"
        expansion = "Volume I"
        purpose = "Elevation Overlay"
        name = stem
        elev = 2
        m_elev = re.search(r"\+(\d+)", filename)
        if m_elev:
            elev = int(m_elev.group(1))
        terrain_details = {
            "terrain_name": "Steep Hill",
            "terrain_category": "Rough / Hill",
            "cover_high": 2,
            "cover_low": 1,
            "burst_modifier": 0,
            "elevation": elev,
            "landing_zone": "None",
            "trafficability": "poor",
            "cover_potential": 2,
            "borders": {"north": "dark", "east": "dark", "south": "dark", "west": "dark"},
            "features": ["Steep Slope"],
        }
    elif re.match(r"^A\d{2}", filename):
        card_type = "terrain"
        deck = "Ardennes Terrain"
        expansion = "Volume II"
        purpose = "Map Terrain Grid"
        raw_name = filename[3:].rsplit(".", 1)[0].replace("-", "").strip() or "Ardennes Terrain"
        name = f"A{filename[1:3]} - {raw_name}"
        terrain_details = make_terrain_details(raw_name, presets)
    elif re.match(r"^C\d{2}", filename):
        card_type = "terrain"
        deck = "Chosin Reservoir Terrain"
        expansion = "Volume II"
        purpose = "Map Terrain Grid"
        raw_name = filename[3:].rsplit(".", 1)[0].replace("-", "").strip() or "Chosin Terrain"
        name = f"C{filename[1:3]} - {raw_name}"
        terrain_details = make_terrain_details(raw_name, presets)
    elif re.match(r"^P\d{2}", filename):
        card_type = "terrain"
        deck = "Peleliu Terrain"
        expansion = "Volume II"
        purpose = "Map Terrain Grid"
        raw_name = filename[3:].rsplit(".", 1)[0].replace("-", "").strip() or "Peleliu Terrain"
        name = f"P{filename[1:3]} - {raw_name}"
        terrain_details = make_terrain_details(raw_name, presets)
    elif re.match(r"^Hue\d{2}", filename):
        card_type = "terrain"
        deck = "Hue Terrain"
        expansion = "Volume II"
        purpose = "Map Terrain Grid"
        name = f"Hue {filename[3:5]}"
        terrain_details = {
            "terrain_name": "Urban Street / Building",
            "terrain_category": "Urban / Building",
            "cover_high": 3,
            "cover_low": 2,
            "burst_modifier": 1,
            "elevation": 0,
            "landing_zone": "None",
            "trafficability": "poor",
            "cover_potential": 3,
            "borders": {"north": "dark", "east": "dark", "south": "dark", "west": "dark"},
            "features": ["Urban Building", "Rubble"],
        }
    elif "falklands" in lower or "goose green" in lower:
        card_type = "terrain"
        deck = "Falklands - Goose Green Terrain"
        expansion = "Volume III"
        purpose = "Map Terrain Grid"
        name = stem

    # Generate canonical card ID
    clean_id = re.sub(r"[^A-Za-z0-9_-]", "-", stem).strip("-").upper()
    prefix = "FOF-CARD"
    if card_type == "terrain":
        prefix = "FOF-TERRAIN"
    elif card_type == "action":
        prefix = "FOF-ACTION"
    elif card_type == "fsa":
        prefix = "FOF-FSA"
    elif card_type == "staging_area":
        prefix = "FOF-STAGING"
    card_id = f"{prefix}-{clean_id}"

    return {
        "id": card_id,
        "name": name,
        "card_type": card_type,
        "deck": deck,
        "expansion": expansion,
        "purpose": purpose,
        "terrain_details": terrain_details,
        "action_details": action_details,
    }


def make_terrain_details(raw_name: str, presets: dict) -> dict:
    canonical = raw_name.lower().replace("/", "_").replace(" ", "_")
    matched_preset = None
    for k, v in presets.items():
        if k in canonical or canonical in k or v.get("name", "").lower() in raw_name.lower():
            matched_preset = v
            break

    cat = "Open"
    if any(k in canonical for k in ["woods", "forest", "jungle", "bamboo", "orchard", "grove", "plantation"]):
        cat = "Forest / Woods"
    elif any(k in canonical for k in ["hill", "rocky", "ridge", "peak", "cliffs"]):
        cat = "Rough / Hill"
    elif any(k in canonical for k in ["village", "farm", "church", "cemetery", "graveyard", "building"]):
        cat = "Urban / Building"
    elif any(k in canonical for k in ["marsh", "swamp", "canal", "paddy", "surf", "beach", "pond"]):
        cat = "Water / Marsh"
    elif any(k in canonical for k in ["bocage", "hedgerow", "embankment", "dunes"]):
        cat = "Linear Obstacle"

    cov_h = matched_preset.get("cover_high", 1) if matched_preset else (2 if cat == "Urban / Building" else (1 if cat == "Forest / Woods" else 0))
    cov_l = matched_preset.get("cover_low", 1) if matched_preset else cov_h
    elev = matched_preset.get("elevation", 1) if matched_preset else (1 if cat == "Rough / Hill" else 0)

    borders_list = matched_preset.get("borders", ["white", "white", "white", "white"]) if matched_preset else ["white", "white", "white", "white"]

    return {
        "terrain_name": raw_name.title() or "Terrain",
        "terrain_category": cat,
        "cover_high": cov_h,
        "cover_low": cov_l,
        "burst_modifier": matched_preset.get("burst", 0) if matched_preset else 0,
        "elevation": elev,
        "landing_zone": "Good" if cat == "Open" else "None",
        "trafficability": matched_preset.get("trafficability", "good" if cat == "Open" else "fair") if matched_preset else "fair",
        "cover_potential": matched_preset.get("cover_potential", 1) if matched_preset else 1,
        "borders": {
            "north": borders_list[0] if len(borders_list) > 0 else "white",
            "east": borders_list[1] if len(borders_list) > 1 else "white",
            "south": borders_list[2] if len(borders_list) > 2 else "white",
            "west": borders_list[3] if len(borders_list) > 3 else "white",
        },
        "features": [raw_name.title()] if raw_name else [],
    }


def main():
    csv_data = load_csv_data()
    presets = load_terrain_presets()

    files = sorted([f.name for f in CARDS_DIR.glob("*") if f.is_file()])
    print(f"Discovered {len(files)} card image files in {CARDS_DIR}")

    records = []
    for fn in files:
        full_path = CARDS_DIR / fn
        try:
            with Image.open(full_path) as im:
                w, h = im.size
                fmt = im.format.lower() if im.format else Path(fn).suffix.strip(".").lower()
        except Exception:
            w, h, fmt = 300, 420, Path(fn).suffix.strip(".").lower()

        csv_row = csv_data.get(fn)
        card_info = classify_card(fn, csv_row, presets)

        record = {
            "id": card_info["id"],
            "name": card_info["name"],
            "card_type": card_info["card_type"],
            "deck": card_info["deck"],
            "expansion": card_info["expansion"],
            "purpose": card_info["purpose"],
            "image": {
                "filename": f"cards/{fn}",
                "width": w,
                "height": h,
                "format": fmt if fmt in ["png", "jpg", "jpeg", "webp"] else "png",
            },
            "terrain_details": card_info["terrain_details"],
            "action_details": card_info["action_details"],
            "classification": {
                "reviewed": False,
                "reviewer": None,
                "reviewed_at": None,
                "notes": f"Auto-indexed from {fn}",
            },
        }
        records.append(record)

    output_path = CONFIG_DIR / "cards.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {len(records)} records to {output_path}")

    final_path = CONFIG_DIR / "cards-final.json"
    if not final_path.exists():
        with final_path.open("w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Initialized empty {final_path}")


if __name__ == "__main__":
    main()
