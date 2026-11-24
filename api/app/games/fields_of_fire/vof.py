"""Volume of Fire (VOF) rules (rulebook 6.2).

A VOF marker records the fire affecting a card. Each rating has a value; the
lower (better) value is the one that applies to a unit (6.2: "The best VOF
affecting a unit is the only one applied").

Only the basic ratings are modelled here: S, A, H, A/S and Pinned. Other
ratings (G!, S!, Incoming!, WP and so on) are rejected until implemented.
"""
from __future__ import annotations

from typing import Any

# 6.2.2 Basic VOF ratings and the value of the marker they place.
VOF_VALUES: dict[str, int] = {"S": 0, "A": -1, "H": -3, "PINNED": 2}
# A/S places an Automatic (-1) marker at point blank and a Small Arms (0)
# marker at any other range.
AS_POINT_BLANK = -1
AS_OTHER = 0
SUPPORTED_RATINGS = tuple(VOF_VALUES) + ("A/S",)


def vof_value(rating: str, point_blank: bool = False) -> int:
    """Return the marker value for a rating. Raises ValueError if unsupported."""
    if rating == "A/S":
        return AS_POINT_BLANK if point_blank else AS_OTHER
    if rating in VOF_VALUES:
        return VOF_VALUES[rating]
    raise ValueError(f"unsupported VOF rating: {rating!r}")


def best_vof(markers: list[dict[str, Any]], position: int) -> dict[str, Any] | None:
    """Return the best (lowest value) VOF marker on a card, or None.

    Only markers placed on the card itself are considered. Each marker is
    compared by its stored ``value``.
    """
    on_card = [
        m for m in markers
        if isinstance(m, dict) and m.get("position") == position and isinstance(m.get("value"), int)
    ]
    if not on_card:
        return None
    return min(on_card, key=lambda m: m["value"])
