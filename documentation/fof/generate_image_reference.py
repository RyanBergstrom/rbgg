"""Generate a root-level index of all files in organized/ linked to README sections."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "organized"
README = ROOT / "README.md"
OUTPUT = ROOT / "IMAGE_REFERENCE.md"

# Each organized folder is assigned to the closest reference-document section.
# Multiple docs may be relevant; the rationale is included in the generated index.
CAMPAIGN_MAP = {
    "heartbreakridge": ("12", "Heartbreak Ridge campaign terrain and mission setup"),
    "longtan": ("14", "Vietnam-era campaign terrain and mission setup; check the card label for the specific operation"),
    "vietnam": ("14", "Vietnam-era campaign terrain and mission setup"),
    "hue": ("14", "Vietnam-era campaign terrain and mission setup"),
    "normandy": ("15", "Normandy campaign terrain, setup, and mission context"),
    "chosin": ("11", "Korean War terrain-card and campaign setup rules; this image set supplements the rulebook context"),
    "korea": ("11", "Korean War terrain-card and campaign setup rules; this image set supplements the rulebook context"),
    "peleliu": ("11", "Terrain-card and campaign setup rules; Peleliu-specific cards are not a standalone source PDF in this collection"),
    "ardennes": ("11", "Terrain-card and campaign setup rules; Ardennes-specific cards are not a standalone source PDF in this collection"),
    "afghanistan": ("11", "Terrain-card and mission setup rules; no matching dedicated campaign PDF is included"),
}

TOKEN_MAP = {
    "vof": ("04", "Volume-of-fire, PDF, combat effects, and VOF modifier reference charts."),
    "smoke": ("11", "Combat and terrain rules involving smoke and visibility."),
    "cover": ("11", "Cover, fortifications, terrain, and combat-modifier rules."),
    "ammo": ("10", "Vehicle and anti-tank weapons reference; ammunition handling and out-of-ammo rules."),
    "vehicle markers": ("10", "Vehicle movement, anti-tank combat, and vehicle status rules."),
    "assets": ("10", "Weapon and asset references, including vehicle/anti-tank equipment."),
    "experience": ("03", "Limited-action-team and multi-step unit experience reference charts."),
    "control": ("05", "Command-display and command/control references."),
    "turn markers": ("09", "Sequence-of-play and turn progression references."),
    "labels": ("08", "Logsheets and mission-log fields; labels are visual aids for recording play."),
    "markers": ("04", "Enemy activity and combat marker references; verify the individual marker name for its exact rule."),
}

SHARED_MAP = {
    "card backs": ("03", "Card-back artwork used with the player-aid card and terrain-card decks."),
    "overlay layers": ("11", "Reusable overlays for map and terrain presentation during setup and play."),
    "player aids": ("03", "Reference/player-aid graphics supporting the charts and tables."),
    "vassal ui": ("01", "Interface icons and controls; these support using the module rather than a specific rule chart."),
    "backgrounds": ("11", "Reusable visual backgrounds for maps/cards; consult the campaign-specific terrain sections for use."),
    "counter bases": ("11", "Reusable counter artwork supporting unit and marker presentation."),
}


def document_sections(text: str) -> dict[str, tuple[str, str]]:
    sections = {}
    for line in text.splitlines():
        match = re.match(r"^## (\d{2})\. (.+\.pdf)\s*$", line)
        if match:
            number, title = match.groups()
            sections[number] = (title, slugify(line[3:].strip()))
    return sections


def slugify(heading: str) -> str:
    value = re.sub(r"[`*_~]", "", heading).strip().lower()
    value = re.sub(r"[^\w\- ]", "", value, flags=re.UNICODE)
    return re.sub(r"\s+", "-", value).strip("-")


def link(path: Path) -> str:
    return quote(path.relative_to(ROOT).as_posix(), safe="/")


def assignment(path: Path) -> tuple[str, str, str]:
    rel = path.relative_to(ASSETS).as_posix()
    parts = path.relative_to(ASSETS).parts
    category = parts[0]
    folder = parts[1] if len(parts) > 2 else category
    key = folder.casefold()

    if category == "Cards":
        if "action cards" in key:
            return "01", "Action-card images used with the action menu, command draws, and turn-by-turn play.", folder
        if key.startswith("pc_") or "contact" in key or "random" in key:
            return "03", "Potential Contact card artwork used with contact-draw and enemy-placement rules.", folder
        if "fire support" in key:
            return "04", "Fire-support terrain/card artwork associated with VOF, PDF, and fire-mission rules.", folder
        if "starter" in key or "staging" in key:
            return "11", "Starter/staging terrain used during map setup and unit movement/infiltration.", folder
        for keyword, result in CAMPAIGN_MAP.items():
            if keyword in key:
                return result[0], result[1], folder
        if key.startswith("volume"):
            return "11", "Volume terrain-card artwork; use the campaign and terrain-card rules to interpret the card faces.", folder
        return "11", "Terrain-card artwork used to build the map; related to terrain layout, LOS, cover, and campaign setup.", folder

    if category == "Tokens":
        doc, blurb = TOKEN_MAP.get(key, ("11", "Game marker/counter artwork; the exact effect depends on the printed marker and the relevant rule."))
        return doc, blurb, folder

    if category == "Shared Assets":
        doc, blurb = SHARED_MAP.get(key, ("11", "Reusable artwork used across multiple cards, maps, or counters."))
        return doc, blurb, folder

    if category == "Review":
        return "11", "Uncertain classification from the organizer; listed for discovery, but verify its role in the source module before relying on this association.", folder

    return "11", "Supporting organized asset; consult its name and the linked file to determine its exact use.", folder


def main() -> None:
    if not ASSETS.is_dir():
        raise SystemExit(f"Missing asset directory: {ASSETS}")
    docs = document_sections(README.read_text(encoding="utf-8"))
    groups: dict[tuple[str, str], list[Path]] = defaultdict(list)
    blurbs: dict[tuple[str, str], str] = {}
    all_files = sorted((p for p in ASSETS.rglob("*") if p.is_file()), key=lambda p: p.relative_to(ASSETS).as_posix().casefold())
    for path in all_files:
        if path.suffix.casefold() == ".csv":
            groups[("00", "Catalog and review reports")].append(path)
            continue
        doc, blurb, folder = assignment(path)
        key = (doc, folder)
        groups[key].append(path)
        blurbs[key] = blurb

    output = [
        "# Organized Image and Asset Reference",
        "",
        "This index lists every file currently present under `organized/` and groups image assets beside the closest related source-document section in [README.md](README.md). The relationship blurbs are navigation hints based on folder names, filenames, and the organizer’s classification; they are not claims that each image appears in that PDF. All asset links are relative to the project root.",
        "",
        f"**Files indexed:** {len(all_files):,}  |  **Image files:** {sum(p.suffix.casefold() != '.csv' for p in all_files):,}  |  **Catalog/report CSVs:** {sum(p.suffix.casefold() == '.csv' for p in all_files):,}",
        "",
        "## Contents",
        "",
    ]
    for key in sorted(groups):
        doc, folder = key
        title = "Catalog and review reports" if doc == "00" else docs.get(doc, (f"README section {doc}", ""))[0]
        anchor = "catalog-and-review-reports" if doc == "00" else docs.get(doc, ("", ""))[1]
        label = f"{title} — {folder}"
        output.append(f"- [{label}](#{slugify(label)})")

    output.extend(["", "## Assets by related README section", ""])
    for key in sorted(groups):
        doc, folder = key
        title, anchor = ("Catalog and review reports", "catalog-and-review-reports") if doc == "00" else docs.get(doc, (f"README section {doc}", ""))
        label = f"{title} — {folder}"
        output.extend([f"### {label}", ""])
        if doc != "00":
            output.append(f"**Related README section:** [{title}](README.md#{anchor})  ")
            output.append(f"**Image group:** `{folder}`  ")
            output.append(f"**Why these files are here:** {blurbs[key]}")
        else:
            output.append("These are the inventory, review, and unresolved-reference CSV reports shipped inside `organized/`, not game artwork.")
        output.append("")
        for path in groups[key]:
            rel = path.relative_to(ROOT).as_posix()
            output.append(f"- [{path.name}]({link(path)}) — `{rel}`")
        output.append("")

    OUTPUT.write_text("\n".join(output), encoding="utf-8")
    print(f"Wrote {OUTPUT.name}: indexed {len(all_files)} files in {len(groups)} groups.")


if __name__ == "__main__":
    main()
