"""Parse the user-maintained Twilight Struggle country reference as configuration."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "countryreference.md"

ALIASES = {
    "Dominican Republic": "Dominican Rep",
    "USA": "United States",
    "United States of America": "United States",
}
SUPERPOWERS = {"United States", "USSR"}


def _canonical(name: str) -> str:
    name = name.strip()
    return ALIASES.get(name, name)


def load_country_reference(path: Path = REFERENCE_PATH) -> dict[str, object]:
    """Load country attributes and an undirected graph from the reference table.

    Asymmetric table entries are unioned into a symmetric graph and reported,
    so correcting the Markdown remains the only required config change.
    """
    countries: dict[str, dict[str, object]] = {}
    listed_edges: set[tuple[str, str]] = set()
    directed_country_edges: set[tuple[str, str]] = set()
    superpower_edges: set[tuple[str, str]] = set()
    row_pattern = re.compile(r"^\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.*?)\s*$")

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = row_pattern.match(line)
        if not match:
            continue
        name_text, region, stability_text, bg_text, adjacent_text = (
            part.strip() for part in match.groups()
        )
        if name_text.lower() == "country" or set(name_text) <= {"-", ":"}:
            continue
        name = _canonical(name_text)
        if name in countries:
            raise ValueError(f"Duplicate country row {name!r} at line {line_number}")
        if name in SUPERPOWERS:
            record = {"name": name, "region": region, "stability": None, "battleground": None}
        else:
            try:
                stability = int(stability_text)
            except ValueError:
                if stability_text not in {"—", "-"}:
                    raise ValueError(f"Invalid stability {stability_text!r} at line {line_number}")
                stability = None
            bg = bg_text.upper()
            if bg not in {"Y", "N", "—", "-"}:
                raise ValueError(f"Invalid battleground flag {bg_text!r} at line {line_number}")
            record = {
                "name": name,
                "region": region,
                "stability": stability,
                "battleground": (bg == "Y") if bg in {"Y", "N"} else None,
            }
        countries[name] = record

        if adjacent_text in {"", "—", "-", "(Special country, not controlled normally)"}:
            continue
        for raw_neighbor in adjacent_text.split(","):
            neighbor = _canonical(raw_neighbor)
            edge = tuple(sorted((name, neighbor)))
            if name in SUPERPOWERS or neighbor in SUPERPOWERS:
                superpower_edges.add(edge)
            else:
                listed_edges.add(edge)
                directed_country_edges.add((name, neighbor))

    country_names = set(countries) - SUPERPOWERS
    unknown = sorted(
        endpoint
        for edge in listed_edges
        for endpoint in edge
        if endpoint not in country_names
    )
    if unknown:
        raise ValueError(f"Adjacency references unknown country names: {sorted(set(unknown))}")

    adjacency = {name: set() for name in sorted(country_names)}
    for a, b in listed_edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    missing_reverse = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = row_pattern.match(line)
        if not match or match.group(1).strip().lower() == "country":
            continue
        source = _canonical(match.group(1))
        if source not in country_names:
            continue
        for raw_neighbor in match.group(5).split(","):
            target = _canonical(raw_neighbor)
            if target in country_names and (target, source) not in directed_country_edges:
                # Union provides symmetry; record one diagnostic per authored direction.
                missing_reverse.append({"from": source, "to": target, "line": line_number})

    return {
        "source": str(path),
        "countries": countries,
        "adjacency": {name: sorted(neighbors) for name, neighbors in adjacency.items()},
        "superpower_adjacency": [list(edge) for edge in sorted(superpower_edges)],
        "asymmetric_source_entries": missing_reverse,
        "status": "config_loaded_review_required" if missing_reverse else "config_loaded",
    }
