"""Configurable country data sourced from documentation/twilight-struggle/countryreference.md.

Country and graph corrections belong in the Markdown table; aliases and schema
normalization live here and should change only when the source format changes.
"""
from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REFERENCE_PATH = (
    _PROJECT_ROOT / "documentation" / "twilight-struggle" / "countryreference.md"
)
ALIASES = {
    "Dominican Republic": "Dominican Rep",
    "USA": "United States",
    "United States of America": "United States",
}
SUPERPOWERS = frozenset({"United States", "USSR"})


def _canonical(name: str) -> str:
    cleaned = name.strip()
    return ALIASES.get(cleaned, cleaned)


_PARSED_CACHE: dict[str, dict[str, Any]] = {}


def load_country_data(path: str | Path | None = None) -> dict[str, Any]:
    """Return normalized country and graph data, parsed once per reference path.

    The returned object is shared and must be treated as read-only reference
    data: the engine calls this thousands of times per game, so it is not
    copied. Use ``load_country_data_copy`` to get an independent, mutable copy.
    """
    source = Path(path or os.environ.get("RBGG_TWILIGHT_COUNTRY_REFERENCE", DEFAULT_REFERENCE_PATH))
    # Key on the path text as given: Path.resolve() asks the filesystem every call (slow on Windows).
    key = str(source)
    if key not in _PARSED_CACHE:
        _PARSED_CACHE[key] = _parse_country_data(source)
    return _PARSED_CACHE[key]


def load_country_data_copy(path: str | Path | None = None) -> dict[str, Any]:
    """Return an independent, mutable copy of the country and graph data."""
    return deepcopy(load_country_data(path))


def _parse_country_data(source: Path) -> dict[str, Any]:
    """Parse the editable reference into normalized country and graph data.

    The graph is undirected: any adjacency declared from either endpoint is
    included in both directions. `source_asymmetries` surfaces one-sided rows
    for optional review without preventing play or discarding the connection.
    """
    countries: dict[str, dict[str, Any]] = {}
    undirected_edges: set[tuple[str, str]] = set()
    directed_edges: set[tuple[str, str]] = set()
    superpower_edges: set[tuple[str, str]] = set()

    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if "|" not in line:
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) < 5:
            continue
        raw_name, region, stability_text, bg_text, adjacency_text = columns[:5]
        if raw_name.lower() == "country" or set(raw_name) <= {"-", ":"}:
            continue
        name = _canonical(raw_name)
        if name in countries:
            raise ValueError(f"Duplicate country row {name!r} at {source}:{line_number}")
        if name in SUPERPOWERS:
            stability = None
            battleground = None
        else:
            try:
                stability = int(stability_text)
            except ValueError:
                if stability_text not in {"—", "-"}:
                    raise ValueError(
                        f"Invalid stability {stability_text!r} at {source}:{line_number}"
                    )
                stability = None
            flag = bg_text.upper()
            if flag not in {"Y", "N", "—", "-"}:
                raise ValueError(f"Invalid battleground flag {bg_text!r} at {source}:{line_number}")
            battleground = flag == "Y" if flag in {"Y", "N"} else None
        countries[name] = {
            "name": name,
            "region": region,
            "stability": stability,
            "battleground": battleground,
        }
        if adjacency_text in {"", "—", "-", "(Special country, not controlled normally)"}:
            continue
        for raw_neighbor in adjacency_text.split(","):
            neighbor = _canonical(raw_neighbor)
            edge = tuple(sorted((name, neighbor)))
            if name in SUPERPOWERS or neighbor in SUPERPOWERS:
                superpower_edges.add(edge)
            else:
                undirected_edges.add(edge)
                directed_edges.add((name, neighbor))

    country_names = set(countries) - SUPERPOWERS
    unknown = sorted(
        {node for edge in undirected_edges for node in edge if node not in country_names}
    )
    if unknown:
        raise ValueError(f"Adjacency references unknown countries: {unknown}")

    adjacency: dict[str, set[str]] = {name: set() for name in sorted(country_names)}
    for first, second in undirected_edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    asymmetries = [
        {"from": first, "to": second}
        for first, second in sorted(directed_edges)
        if (second, first) not in directed_edges
    ]

    return {
        "countries": {name: countries[name] for name in sorted(country_names)},
        "adjacency": {name: sorted(neighbors) for name, neighbors in adjacency.items()},
        "superpowers": {name: countries[name] for name in sorted(SUPERPOWERS) if name in countries},
        "superpower_adjacency": [list(edge) for edge in sorted(superpower_edges)],
        "source_asymmetries": asymmetries,
        "source_path": str(source),
    }


def are_adjacent(first: str, second: str, data: dict[str, Any] | None = None) -> bool:
    """Return whether two country spaces are adjacent in the loaded graph."""
    graph = data or load_country_data()
    a, b = _canonical(first), _canonical(second)
    return b in graph["adjacency"].get(a, ())
