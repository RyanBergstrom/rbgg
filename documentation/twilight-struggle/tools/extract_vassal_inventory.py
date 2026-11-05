"""Extract provisional country/card metadata from the supplied VASSAL XML.

This tool reads country traits but does not infer adjacency or card event
behavior. It prints JSON to stdout and never modifies source files.
"""
from __future__ import annotations

import json
import re
import sys
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XML_PATH = ROOT / "buildFile.xml"


def parse_card(element: ET.Element) -> dict[str, object]:
    raw = (element.text or "").split("\t", 1)[0]
    fields = raw.split(";", 8)
    if len(fields) < 8:
        raise ValueError(f"Unexpected CardSlot encoding: {element.attrib.get('entryName')}")
    try:
        card_id = int(fields[1])
    except ValueError as error:
        raise ValueError(
            f"Missing card number for {element.attrib.get('entryName')}"
        ) from error
    trait_fields = (element.text or "").split("\t")
    card_face = next(
        (field for field in trait_fields if re.search(r"TNRnTS-\d+\.svg", field)),
        None,
    )
    if card_face is None:
        raise ValueError(f"Missing card-face asset for {element.attrib.get('entryName')}")
    card_face_name = re.search(r"TNRnTS-\d+\.svg", card_face).group(0)
    svg_root = ET.parse(ROOT / "images" / card_face_name).getroot()
    text_nodes = [
        node
        for node in svg_root.iter()
        if node.tag.endswith("}text") or node.tag == "text"
    ]
    return {
        "card_id": card_id,
        "name": element.attrib.get("entryName", ""),
        "era_code": int(fields[3]),
        "operations": int(fields[4]),
        "alignment_code": int(fields[5]),
        "event_removed_flag": fields[6].lower() == "true",
        "scoring_flag": fields[7].lower() == "true",
        "gpid": element.attrib.get("gpid"),
        "card_face_asset": f"images/{card_face_name}",
        "card_face_text_node_count": len(text_nodes),
        "rules_effect_status": "not_encoded_in_extracted_fields",
    }


def parse_country_attributes(root: ET.Element) -> dict[str, dict[str, object]]:
    """Read country stability/region/battleground fields from influence traits.

    VASSAL setup stacks encode those fields as ``influence;stability;region;bg``.
    Stack names take precedence over VASSAL's sometimes blank/incorrect
    ``location`` values. Conflicting traits are surfaced as errors.
    This does not infer the adjacency graph.
    """
    result: dict[str, dict[str, object]] = {}
    known_countries = {
        region.attrib.get("name")
        for region in root.find(
            ".//VASSAL.build.module.map.boardPicker.board.RegionGrid"
        ).findall("VASSAL.build.module.map.boardPicker.board.Region")
    }
    for stack in root.iter():
        if not stack.tag.endswith("SetupStack"):
            continue
        location = stack.attrib.get("location", "").strip()
        stack_country = stack.attrib.get("name", "").split("/", 1)[0].strip()
        country_name = stack_country if stack_country in known_countries else location
        if not country_name or country_name not in known_countries:
            continue
        for slot in stack:
            if not slot.tag.endswith("PieceSlot"):
                continue
            raw = (slot.text or "").split("\t", 1)[0]
            match = re.search(r"(?:^|/)influence;(\d+);([^;]+);(true|false)", raw, re.I)
            if match is None:
                continue
            stability = int(match.group(1))
            region = match.group(2).strip()
            battleground = match.group(3).lower() == "true"
            attributes = {
                "stability": stability,
                "trait_region": region,
                "battleground": battleground,
                "attributes_source": "VASSAL influence trait; verify against board/rulebook",
            }
            previous = result.get(country_name)
            if previous is not None and previous != attributes:
                raise ValueError(f"Conflicting country metadata for {country_name}")
            result[country_name] = attributes
    return result


def extract() -> dict[str, object]:
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    region_grid = root.find(
        ".//VASSAL.build.module.map.boardPicker.board.RegionGrid"
    )
    if region_grid is None:
        raise ValueError("Main map RegionGrid not found")
    country_attributes = parse_country_attributes(root)
    countries = [
        {
            "name": region.attrib["name"],
            "map_x": int(region.attrib["originx"]),
            "map_y": int(region.attrib["originy"]),
            **country_attributes.get(region.attrib["name"], {}),
            "country_data_status": (
                "provisional_from_vassal_trait"
                if region.attrib["name"] in country_attributes
                else "review_required_missing_trait"
            ),
            "adjacency_status": "not_encoded_in_xml",
        }
        for region in region_grid.findall(
            "VASSAL.build.module.map.boardPicker.board.Region"
        )
    ]
    cards = [
        parse_card(element)
        for element in root.iter()
        if element.tag.endswith("CardSlot")
    ]
    if len({card["card_id"] for card in cards}) != len(cards):
        raise ValueError("Duplicate card IDs in CardSlot inventory")
    return {
        "source": "VASSAL buildFile.xml",
        "module": root.attrib.get("name"),
        "warning": "Metadata/layout extraction only; not a rules catalog.",
        "countries": countries,
        "cards": sorted(cards, key=lambda card: int(card["card_id"])),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries-only",
        action="store_true",
        help="print country-map draft records without card metadata",
    )
    parser.add_argument(
        "--review-config",
        action="store_true",
        help="print compact country records for the review configuration",
    )
    args = parser.parse_args()
    inventory = extract()
    if args.review_config:
        payload = {
            "source": "VASSAL buildFile.xml country traits and supplied TS Map-11.jpg",
            "status": "provisional_review_draft",
            "warning": (
                "Country labels, map coordinates, stability, region, and battleground "
                "flags are extracted from VASSAL and accepted as correct per user "
                "confirmation. Adjacency is intentionally empty: the board image "
                "is visual evidence, not a machine-readable graph."
            ),
            "country_fields": [
                "name", "map_x", "map_y", "stability", "trait_region",
                "battleground"
            ],
            "scoring_region_memberships": "same_as_trait_region",
            "scoring_region_status": "user_confirmed_vassal_region_values",
            "adjacency": {
                country["name"]: [] for country in inventory["countries"]
            },
            "countries": [
                [
                    country["name"], country["map_x"], country["map_y"],
                    country.get("stability"), country.get("trait_region"),
                    country.get("battleground"),
                ]
                for country in inventory["countries"]
            ],
        }
    else:
        payload = inventory["countries"] if args.countries_only else inventory
    json.dump(payload, sys.stdout, separators=(",", ":") if args.review_config else None, indent=None if args.review_config else 2)
    sys.stdout.write("\n")
