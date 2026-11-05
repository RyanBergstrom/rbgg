"""Standard base-game card metadata extracted from the supplied VASSAL module.

This is metadata only. Card events remain unimplemented unless a card has an
explicit structured handler; callers must not treat missing handlers as no-ops.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_VASSAL_XML = _PROJECT_ROOT / "documentation" / "twilight-struggle" / "buildFile.xml"
_STANDARD_CARD_IDS = frozenset(range(1, 111))
_ERA_BY_CODE = {0: 1, 1: 2, 2: 3}
_ALIGNMENT_BY_CODE = {0: "both", 1: "us", 2: "ussr"}


def load_standard_card_catalog(xml_path: str | Path = _DEFAULT_VASSAL_XML) -> list[dict[str, Any]]:
    """Load the 110 standard card records (VASSAL IDs 1-110).

    IDs 104-110 are included per the CSV master record (validated = 1). The
    China Card is metadata but not a deck card. IDs and rule metadata are checked strictly to avoid a partial deck.
    """
    root = ET.parse(xml_path).getroot()
    cards: dict[int, dict[str, Any]] = {}
    for element in root.iter():
        if not element.tag.endswith("CardSlot"):
            continue
        raw = (element.text or "").split("\t", 1)[0]
        fields = raw.split(";", 8)
        if len(fields) < 8:
            continue
        try:
            card_id = int(fields[1])
        except (IndexError, ValueError):
            continue
        if card_id not in _STANDARD_CARD_IDS:
            continue
        try:
            era_code = int(fields[3])
            operations = int(fields[4])
            alignment_code = int(fields[5])
        except (IndexError, ValueError) as error:
            raise ValueError(f"Invalid VASSAL metadata for standard card {card_id}") from error
        if era_code not in _ERA_BY_CODE or alignment_code not in _ALIGNMENT_BY_CODE:
            raise ValueError(f"Unsupported era/alignment for standard card {card_id}")
        name = element.attrib.get("entryName", "").strip()
        face_match = re.search(r"TNRnTS-\d+\.svg", element.text or "")
        if not name or face_match is None or operations < 0:
            raise ValueError(f"Incomplete VASSAL metadata for standard card {card_id}")
        if card_id in cards:
            raise ValueError(f"Duplicate standard VASSAL card id {card_id}")
        china_card = name.casefold() == "the china card"
        cards[card_id] = {
            "id": card_id,
            "name": name,
            "era": _ERA_BY_CODE[era_code],
            "operations": operations,
            "alignment": _ALIGNMENT_BY_CODE[alignment_code],
            "event_removed": fields[6].lower() == "true",
            "scoring": fields[7].lower() == "true",
            "special": china_card,
            "deck_card": not china_card,
            "card_face_asset": face_match.group(0),
            "effect_handler": {
                4: "duck_and_cover",
                5: "five_year_plan",
                8: "fidel",
                10: "blockade",
                12: "romanian_abdication",
                14: "comecon",
                15: "nasser",
                17: "de_gaulle_leads_france",
                21: "nato",
                25: "containment",
                42: "quagmire",
                44: "bear_trap",
                31: "red_scare_purge",
                34: "nuclear_test_ban",
                35: "formosan_resolution",
                103: "defectors",
                104: "cambridge_five",
                105: "special_relationship",
                43: "salt_negotiations",
                46: "how_i_learned_to_stop_worrying",
                48: "kitchen_debates",
                49: "missile_envy",
                106: "norad",
                32: "un_intervention",
                50: "we_will_bury_you",
                51: "brezhnev_doctrine",
                54: "allende",
                55: "willy_brandt",
                64: "panama_canal_returned",
                65: "camp_david_accords",
                68: "john_paul_ii_elected_pope",
                70: "oas_founded",
                72: "sadat_expels_soviets",
                73: "shuttle_diplomacy",
                74: "the_voice_of_america",
                75: "liberation_theology",
                82: "iranian_hostage_crisis",
                83: "the_iron_lady",
                84: "reagan_bombs_libya",
                88: "marine_barracks_bombing",
                90: "glasnost",
                97: "an_evil_empire",
                99: "pershing_ii_deployed",
                100: "wargames",
                101: "solidarity",
                102: "iran_iraq_war",
                19: "truman_doctrine",
                29: "east_european_unrests",
                30: "decolonization",
                53: "south_african_unrest",
                63: "colonial_rearguards",
                66: "puppet_governments",
                67: "grain_sales",
                7: "socialist_governments",
                16: "warsaw_pact_formed",
                22: "independent_reds",
                28: "suez_crisis",
                39: "arms_race",
                58: "cultural_revolution",
                61: "opec",
                59: "flower_power",
                60: "u2_incident",
                86: "north_sea_oil",
                78: "alliance_for_progress",
                52: "portuguese_empire_crumbles",
                56: "muslim_revolution",
                57: "abm_treaty",
                71: "nixon_plays_china",
                92: "terrorism",
                98: "aldrich_ames_remix",
                110: "awacs_sale_to_saudis",
                11: "korean_war",
                13: "arab_israeli_war",
                24: "indo_pakistani_war",
                36: "brush_war",
                45: "summit",
                27: "us_japan_pact",
                40: "cuban_missile_crisis",
                41: "nuclear_subs",
                47: "junta",
                69: "latin_american_death_squads",
                91: "ortega_nicaragua",
                93: "iran_contra_scandal",
                94: "chernobyl",
                96: "tear_down_this_wall",
                9: "vietnam_revolts",
                23: "marshall_plan",
                33: "de_stalinization",
                20: "olympic_games",
                26: "cia_created",
                62: "lone_gunman",
                18: "captured_nazi_scientist",
                76: "ussuri_river_skirmish",
                77: "ask_not_what",
                80: "one_small_step",
                107: "che",
                108: "our_man_in_tehran",
                85: "star_wars",
                87: "reformer",
                89: "kal_007",
                95: "latin_america_debt_crisis",
                109: "samantha_yuri",
            }.get(card_id),
        }
    missing = sorted(_STANDARD_CARD_IDS - cards.keys())
    if missing:
        raise ValueError(f"VASSAL catalog is missing standard card ids: {missing}")
    return [cards[card_id] for card_id in sorted(cards)]


def standard_deck(era: int | None = None, xml_path: str | Path = _DEFAULT_VASSAL_XML) -> list[dict[str, Any]]:
    """Return deck cards (excluding China Card), optionally limited by era."""
    if era is not None and era not in {1, 2, 3}:
        raise ValueError("era must be 1, 2, or 3")
    return [
        card for card in load_standard_card_catalog(xml_path)
        if card["deck_card"] and (era is None or card["era"] == era)
    ]
