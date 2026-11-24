"""Primary Direction of Fire (PDF) rules (rulebook 6.3).

A PDF marker sits on the edge of the firing card and points toward a target
card. It is placed when a unit exerts a Basic VOF (S, A, H or Pinned) at a
card other than its own (6.3.1).

Cards are laid out on a grid of ``cols`` columns with index = row * cols + col,
where row 0 is the bottom row of the map as used by the board (the same
convention as the rest of the Fields of Fire board code).
"""
from __future__ import annotations

COMPASS = {
    "N": (1, 0),
    "S": (-1, 0),
    "E": (0, 1),
    "W": (0, -1),
}


def target_card(position: int, direction: str, rows: int, cols: int) -> int | None:
    """Return the card index a PDF points at, or None if it leaves the map."""
    if direction not in COMPASS:
        raise ValueError(f"unsupported PDF direction: {direction!r}")
    if rows <= 0 or cols <= 0 or not 0 <= position < rows * cols:
        return None
    row, col = divmod(position, cols)
    d_row, d_col = COMPASS[direction]
    new_row, new_col = row + d_row, col + d_col
    if not (0 <= new_row < rows and 0 <= new_col < cols):
        return None
    return new_row * cols + new_col
