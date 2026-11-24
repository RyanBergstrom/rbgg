"""Combat Resolution lookup (rulebook 2.8.3, 6.4.2).

Each Action card carries a Combat Resolution column: net modifiers from -4 to
+6, each mapped to HIT, PIN or MISS. Given the net modifier (Volume of Fire
plus Cover & Concealment and other conditions), this returns the result.

This is read-only: it does not resolve fire, place markers or change state.
"""
from __future__ import annotations

import re

RESULTS = ("HIT", "PIN", "MISS")
MIN_MODIFIER = -4
MAX_MODIFIER = 6
_PAIR = re.compile(r"([+-]?\d+)\s+(HIT|PIN|MISS)")


def parse_combat_resolution(text: str) -> dict[int, str]:
    """Parse a combat_resolution string into {modifier: result}.

    Raises ValueError if the column is malformed or does not cover every
    modifier from -4 to +6 exactly once.
    """
    table: dict[int, str] = {}
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        match = _PAIR.fullmatch(part)
        if not match:
            raise ValueError(f"malformed combat resolution entry: {part!r}")
        modifier = int(match.group(1))
        if modifier in table:
            raise ValueError(f"duplicate combat resolution modifier: {modifier}")
        table[modifier] = match.group(2)
    expected = set(range(MIN_MODIFIER, MAX_MODIFIER + 1))
    if set(table) != expected:
        raise ValueError(f"combat resolution must cover {MIN_MODIFIER} to {MAX_MODIFIER}")
    return table


def resolve_combat(text: str, net_modifier: int) -> str:
    """Return HIT, PIN or MISS for a net modifier on a card's resolution column.

    Modifiers beyond -4 or +6 use the nearest printed value, since the column
    only prints that range.
    """
    table = parse_combat_resolution(text)
    clamped = max(MIN_MODIFIER, min(MAX_MODIFIER, int(net_modifier)))
    return table[clamped]
