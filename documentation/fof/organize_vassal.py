#!/usr/bin/env python3
"""Organize Fields of Fire VASSAL image assets by their XML context.

Run from any directory:
    python organize_vassal.py

Defaults to buildFile.xml and images/ next to this script. Originals are never
modified; organized/ is created beside this script. Optional paths can be passed
positionally: XML path, image directory, output directory.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tif", ".tiff"}
LABEL_ATTRIBUTES = ("entryName", "name", "label", "title", "description", "text", "command", "deckName")
STRUCTURAL = {
    "PrototypeFolder", "PrototypeDefinition", "PieceSlot", "CardSlot", "DrawPile", "ModuleSubFolder",
    "SetupStack", "Map", "Board", "BoardPicker", "PieceWindow", "ListWidget",
    "PanelWidget", "TabWidget",
}
TOKEN_TERMS = {
    "ammo": "Ammo", "smoke": "Smoke", "vof": "VoF", "volume of fire": "VoF",
    "control": "Control", "cover": "Cover", "experience": "Experience",
    "asset": "Assets", "objective": "Objectives", "vehicle marker": "Vehicle Markers",
    "wreck": "Vehicle Markers", "turn marker": "Turn Markers", "turn track": "Turn Markers",
    "label": "Labels", "status": "Status Markers", "marker": "Markers", "counter": "Markers",
}
SHARED_TERMS = {
    "overlay": "Overlay Layers", "layer": "Overlay Layers", "counter basic": "Counter Bases",
    "counter base": "Counter Bases", "card back": "Card Backs", "back image": "Card Backs",
    "toolbar": "VASSAL UI", "button": "VASSAL UI", "icon": "VASSAL UI", "cursor": "VASSAL UI",
    "border": "Borders", "frame": "Borders", "background": "Backgrounds", "player aid": "Player Aids",
    "reference": "Player Aids", "chart": "Player Aids", "table": "Player Aids",
}

@dataclass(frozen=True)
class Occurrence:
    filename: str
    category: str
    subcategory: str
    campaign: str
    faction: str
    unit_type: str
    context: str
    source_kind: str
    confidence: str
    reason: str


def clean(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ._-\t\r\n")
    return value or "Unspecified"


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(".", 1)[-1]


def node_labels(node: ET.Element) -> list[str]:
    return [str(node.attrib[key]).strip() for key in LABEL_ATTRIBUTES
            if node.attrib.get(key, "").strip()]


def image_tokens(value: str) -> Iterable[str]:
    # VASSAL piece traits serialize several settings and image paths in one
    # semicolon/tab-delimited string; isolate each field before extracting it.
    for field in re.split(r"[;,\\\t\r\n]+", value):
        field = field.strip().strip("\"'")
        if not field:
            continue
        field = field.replace("\\", "/").rsplit("/", 1)[-1].strip().strip("\"'")
        match = re.search(r"([^<>\"|]*?\.(?:png|jpe?g|gif|bmp|webp|svg|tiff?))\s*$", field, re.I)
        if match:
            candidate = match.group(1).strip().strip("' ")
            # VASSAL's G-prefixed flipped-image encoding points at the same asset.
            yield candidate
            if candidate[:1].casefold() == "g":
                yield candidate[1:]


def context_for(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> tuple[list[tuple[str, str]], str]:
    chain: list[ET.Element] = []
    current: ET.Element | None = node
    while current is not None:
        chain.append(current)
        current = parents.get(current)
    chain.reverse()
    named: list[tuple[str, str]] = []
    readable: list[str] = []
    for item in chain:
        tag = local_tag(item.tag)
        label = " / ".join(node_labels(item))
        if tag in STRUCTURAL or label:
            readable.append(tag + (f" [{label}]" if label else ""))
        if label:
            named.append((tag, label))
    return named, " > ".join(readable)


def classify(filename: str, node: ET.Element, named: list[tuple[str, str]], context: str) -> Occurrence:
    ancestry_tags = [part.split(" [", 1)[0] for part in context.split(" > ")]
    labels = [label for _, label in named]
    label_text = " / ".join(labels)
    lower = (label_text + " " + context + " " + filename).casefold()

    campaign = ""
    campaign_tags = {"ModuleSubFolder", "TabWidget", "PanelWidget", "ListWidget", "PieceWindow", "Map", "DrawPile", "SetupStack"}
    for tag, label in named:
        if tag in campaign_tags and label and label.casefold() not in {"unit pieces", "marker pieces", "game pieces", "cards"}:
            campaign = clean(label.split(" / ")[0])
    faction = ""
    faction_candidates = []
    for tag, label in named:
        candidate = clean(label.split(" / ")[0])
        if (tag == "PanelWidget" and label and candidate.casefold() not in
                {"core units", "game markers", "enemy and friendly counters", "marker pieces"}):
            faction_candidates.append(candidate)
    for candidate in faction_candidates:
        if re.search(r"german|japanese|british|american|u\.s\.|north korean|chinese|nva|viet cong|taliban|airborne|marines|regiment|battalion|company|allied|axis", candidate, re.I):
            faction = candidate
            break
    unit_types = [clean(label.split(" / ")[0]) for tag, label in named
                  if tag in {"ListWidget", "PanelWidget"} and label and
                  clean(label.split(" / ")[0]).casefold() not in faction.casefold()]
    unit_type = unit_types[-1] if unit_types else ""
    source_kind = next((tag for tag in reversed(ancestry_tags)
                        if tag in {"PrototypeDefinition", "PieceSlot", "CardSlot", "DrawPile", "SetupStack", "Board", "Map"}), "")

    if local_tag(node.tag) == "Board" or (
        local_tag(node.tag) == "Map" and any(key.casefold() == "image" for key in node.attrib)
    ):
        board_label = next((clean(label.split(" / ")[0]) for tag, label in reversed(named)
                            if tag in {"Board", "Map"} and label), "")
        campaign = campaign or board_label
        return Occurrence(filename, "Maps", board_label or "Boards", campaign, "", "", context,
                          source_kind or "Map", "HIGH", "Direct image reference under Map/Board hierarchy.")

    if "CardSlot" in ancestry_tags or "DrawPile" in ancestry_tags:
        deck = next((clean(label.split(" / ")[0]) for tag, label in reversed(named)
                     if tag in {"DrawPile", "TabWidget", "PanelWidget", "ListWidget", "Map"} and label), "")
        if not deck:
            deck = "Decks Requiring Review"
        return Occurrence(filename, "Cards", deck, campaign, "", "", context, source_kind or "CardSlot",
                          "HIGH" if "CardSlot" in ancestry_tags else "MEDIUM",
                          "CardSlot/DrawPile XML containment identifies the card-deck role.")

    if "PrototypeDefinition" in ancestry_tags:
        shared_sub = next((folder for term, folder in SHARED_TERMS.items() if term in lower), "Reusable Piece Components")
        return Occurrence(filename, "Shared Assets", shared_sub, "", "", "", context, "PrototypeDefinition",
                          "HIGH" if shared_sub != "Reusable Piece Components" else "MEDIUM",
                          "Referenced from a reusable PrototypeDefinition; kept outside campaign-specific folders.")

    if "PieceSlot" in ancestry_tags or "SetupStack" in ancestry_tags:
        token_sub = next((folder for term, folder in TOKEN_TERMS.items() if term in lower), "")
        if token_sub:
            return Occurrence(filename, "Tokens", token_sub, campaign, faction, "", context,
                              source_kind or "PieceSlot", "HIGH",
                              "Piece-slot ancestor labels identify a marker/token category.")
        if faction or unit_type:
            return Occurrence(filename, "Units", unit_type or "Unit Pieces", campaign or "Campaign Unresolved",
                              faction or "Faction Unresolved", unit_type or "Unit Pieces", context,
                              source_kind or "PieceSlot", "HIGH" if faction and campaign else "MEDIUM",
                              "PieceSlot/SetupStack is nested in the piece-window hierarchy; ancestor labels supply grouping.")

    shared_sub = next((folder for term, folder in SHARED_TERMS.items() if term in lower), "")
    if shared_sub:
        return Occurrence(filename, "Shared Assets", shared_sub, "", "", "", context, source_kind,
                          "MEDIUM", "Shared/UI artwork identified by XML labels or prototype trait context.")
    token_sub = next((folder for term, folder in TOKEN_TERMS.items() if term in lower), "")
    if token_sub:
        return Occurrence(filename, "Tokens", token_sub, campaign, faction, "", context, source_kind,
                          "MEDIUM", "XML ancestor labels identify a token/marker category.")
    if "PieceSlot" in ancestry_tags:
        return Occurrence(filename, "Review", "Piece Slot", campaign, faction, unit_type, context,
                          source_kind or "PieceSlot", "LOW", "PieceSlot reference has no reliable named faction or unit/token category.")
    return Occurrence(filename, "Review", "Unclassified XML Reference", campaign, faction, "", context,
                      source_kind, "LOW", "An XML image reference was found, but its structural role is not confidently identifiable.")


def destination(row: Occurrence) -> Path:
    if row.category == "Units":
        return Path("Units") / clean(row.campaign) / clean(row.faction) / clean(row.unit_type)
    if row.category == "Cards":
        return Path("Cards") / clean(row.subcategory)
    if row.category == "Maps":
        return Path("Maps") / clean(row.subcategory)
    return Path(clean(row.category)) / clean(row.subcategory)


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", nargs="?", type=Path, default=base / "buildFile.xml")
    parser.add_argument("images", nargs="?", type=Path, default=base / "images")
    parser.add_argument("output", nargs="?", type=Path, default=base / "organized")
    parser.add_argument("--no-copy", action="store_true", help="Write reports without copying images.")
    args = parser.parse_args()
    xml_path, image_root, output_root = (p.resolve() for p in (args.xml, args.images, args.output))
    if not xml_path.is_file():
        parser.error(f"XML file not found: {xml_path}")
    if not image_root.is_dir():
        parser.error(f"Image directory not found: {image_root}")

    images: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(image_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            images[path.name.casefold()].append(path)
    if not images:
        parser.error(f"No supported images found under: {image_root}")

    try:
        tree = ET.parse(xml_path)
    except (ET.ParseError, OSError) as exc:
        print(f"Could not parse XML: {exc}", file=sys.stderr)
        return 2
    root = tree.getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    found: dict[str, list[Occurrence]] = defaultdict(list)
    unresolved_refs: list[dict[str, str]] = []

    for node in root.iter():
        values = list(node.attrib.values())
        if node.text and node.text.strip():
            values.append(node.text)
        named, context = context_for(node, parents)
        for value in values:
            for token in image_tokens(value):
                key = token.casefold()
                if key not in images:
                    unresolved_refs.append({"filename": token, "context": context,
                                            "reason": "XML reference has no same-basename file under the image directory."})
                    continue
                found[key].append(classify(token, node, named, context))

    manifest: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    copies: dict[tuple[str, str], Path] = {}
    for key, paths in sorted(images.items()):
        occurrences = found.get(key, [])
        if not occurrences:
            continue
        # Primary purpose precedence: explicit card/map/unit placement beats generic prototype reuse.
        priority = {"Maps": 0, "Cards": 1, "Units": 2, "Tokens": 3, "Shared Assets": 4, "Review": 5}
        primary = sorted(occurrences, key=lambda item: (priority.get(item.category, 9),
                         item.confidence != "HIGH", len(item.context)))[0]
        folder = destination(primary).as_posix()
        contexts = sorted({o.context for o in occurrences})
        usages = sorted({f"{o.category}/{o.subcategory}" for o in occurrences})
        # Multiple distinct source files with the same basename are preserved separately and flagged.
        for source in paths:
            manifest.append({"filename": source.name, "folder": folder, "category": primary.category,
                             "subcategory": primary.subcategory, "campaign": primary.campaign,
                             "faction": primary.faction, "unit_type": primary.unit_type,
                             "confidence": primary.confidence,
                             "reason": primary.reason,
                             "duplicate_usages": " || ".join(usages),
                             "xml_contexts": " || ".join(contexts),
                             "source": source.relative_to(image_root).as_posix()})
            copies[(source.relative_to(image_root).as_posix(), folder)] = source
        if primary.confidence == "LOW":
            review.append({"filename": paths[0].name, "proposed_folder": folder,
                           "reason": primary.reason, "xml_contexts": " || ".join(contexts)})

    unmatched_rows = []
    referenced_keys = set(found)
    for key, paths in sorted(images.items()):
        if key not in referenced_keys:
            for path in paths:
                unmatched_rows.append({"filename": path.name, "source": path.relative_to(image_root).as_posix(),
                                       "reason": "No resolvable XML reference found."})

    if not args.no_copy:
        for (relative, folder), source in copies.items():
            target_dir = output_root / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            if target.exists():
                # Never overwrite a different asset with a same-named file.
                if target.resolve() != source.resolve():
                    target = target_dir / f"{source.stem}__{re.sub(r'[^A-Za-z0-9_-]+', '_', Path(relative).parent.name)}{source.suffix}"
            if not target.exists():
                shutil.copy2(source, target)

    output_root.mkdir(parents=True, exist_ok=True)
    fields = ["filename", "folder", "category", "subcategory", "campaign", "faction", "unit_type",
              "confidence", "reason", "duplicate_usages", "xml_contexts", "source"]
    write_csv(output_root / "manifest.csv", fields, manifest)
    write_csv(output_root / "unmatched.csv", ["filename", "source", "reason"], unmatched_rows)
    write_csv(output_root / "review.csv", ["filename", "proposed_folder", "reason", "xml_contexts"], review)
    write_csv(output_root / "unresolved-references.csv", ["filename", "context", "reason"], unresolved_refs)

    counts = Counter(row["category"] for row in manifest)
    print("Fields of Fire asset organization complete")
    print(f"XML: {xml_path}\nImages: {image_root}\nOutput: {output_root}")
    print(f"Image files: {sum(map(len, images.values()))}")
    print(f"Referenced image files: {len({row['source'] for row in manifest})}")
    print(f"Manifest rows: {len(manifest)} | Unmatched files: {len(unmatched_rows)}")
    print(f"Low-confidence review rows: {len(review)} | Unresolved XML refs: {len(unresolved_refs)}")
    for category, count in sorted(counts.items()):
        print(f"  {category}: {count}")
    print("Reports: manifest.csv, unmatched.csv, review.csv, unresolved-references.csv")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
