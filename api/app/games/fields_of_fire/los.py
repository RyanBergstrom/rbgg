"""Line of Sight between board cards (rulebook 5.2.1).

LOS is traced along the eight straight directions only. Adjacent cards are
always in LOS. Beyond that, each card the line passes through must have white
borders on both the entry and exit sides. Dark and black borders block LOS.

Border order matches the terrain loader and cards-final.json: a card's
``borders`` list is [north, east, south, west].

Range is at most three cards (Very Long Range), or one card (Close Range) in
limited visibility (9.1).
"""
from __future__ import annotations

from typing import Callable

# Eight straight directions: (row delta, col delta).
DIRECTIONS = {
    "N": (1, 0),
    "NE": (1, 1),
    "E": (0, 1),
    "SE": (-1, 1),
    "S": (-1, 0),
    "SW": (-1, -1),
    "W": (0, -1),
    "NW": (1, -1),
}
# Border index for the side a line leaves through and enters through.
_BORDER_INDEX = {"N": 0, "E": 1, "S": 2, "W": 3}
# Edges a diagonal line exits/enters. Diagonals cross a corner, so both
# adjacent edges must be white.
_DIAGONAL_EDGES = {
    "NE": ("N", "E"),
    "SE": ("S", "E"),
    "SW": ("S", "W"),
    "NW": ("N", "W"),
}
MAX_RANGE = 3
MAX_RANGE_LIMITED = 1


def _edges_for(direction: str, leaving: bool) -> tuple[str, ...]:
    """Edges of a card a straight or diagonal line touches when crossing it."""
    if direction in _DIAGONAL_EDGES:
        return _DIAGONAL_EDGES[direction]
    # Straight line: leaving a card goes out the side in the direction of travel;
    # entering the next card comes in from the opposite side.
    edge = direction
    if leaving:
        return (edge,)
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}[edge]
    return (opposite,)


def _cell(position: int, rows: int, cols: int, delta: tuple[int, int], steps: int) -> int | None:
    row, col = divmod(position, cols)
    new_row = row + delta[0] * steps
    new_col = col + delta[1] * steps
    if not (0 <= new_row < rows and 0 <= new_col < cols):
        return None
    return new_row * cols + new_col


def los_path(origin: int, target: int, rows: int, cols: int) -> list[int] | None:
    """Return the cards on the straight line from origin to target, or None.

    The result includes origin and target. None means the target is not on
    one of the eight straight lines from origin.
    """
    if origin == target:
        return [origin]
    if not (0 <= origin < rows * cols and 0 <= target < rows * cols):
        return None
    o_row, o_col = divmod(origin, cols)
    t_row, t_col = divmod(target, cols)
    d_row, d_col = t_row - o_row, t_col - o_col
    steps = max(abs(d_row), abs(d_col))
    if steps == 0:
        return [origin]
    # Must be exactly a straight or diagonal line.
    if d_row not in (0, steps, -steps) or d_col not in (0, steps, -steps):
        return None
    if d_row and d_col and abs(d_row) != abs(d_col):
        return None
    unit = (
        (d_row // steps) if d_row else 0,
        (d_col // steps) if d_col else 0,
    )
    return [_cell(origin, rows, cols, unit, k) for k in range(steps + 1)]


def has_los(
    origin: int,
    target: int,
    rows: int,
    cols: int,
    borders: Callable[[int], list[str]],
    limited: bool = False,
) -> bool:
    """True if target is in line of sight from origin under rulebook 5.2.1.

    ``borders(position)`` returns the four border colours of a card, in
    [north, east, south, west] order. Missing cards count as blocked.
    """
    path = los_path(origin, target, rows, cols)
    if path is None:
        return False
    distance = len(path) - 1
    if distance == 0:
        return True
    max_range = MAX_RANGE_LIMITED if limited else MAX_RANGE
    if distance > max_range:
        return False
    # Adjacent cards are always in LOS.
    if distance == 1:
        return True
    direction = _direction_between(origin, path[1], rows, cols)
    # Each intermediate card must pass the line from entry to exit side, and the
    # origin card must let the line leave. The target card only needs its entry side.
    for index, card in enumerate(path[1:-1], start=1):
        colours = borders(card)
        entry = _edges_for(direction, leaving=False)
        exit_ = _edges_for(direction, leaving=True)
        if any(colours[_BORDER_INDEX[edge]] != "white" for edge in entry + exit_):
            return False
    origin_colours = borders(origin)
    if any(origin_colours[_BORDER_INDEX[edge]] != "white" for edge in _edges_for(direction, leaving=True)):
        return False
    target_colours = borders(target)
    if any(target_colours[_BORDER_INDEX[edge]] != "white" for edge in _edges_for(direction, leaving=False)):
        return False
    return True


def _direction_between(a: int, b: int, rows: int, cols: int) -> str:
    a_row, a_col = divmod(a, cols)
    b_row, b_col = divmod(b, cols)
    d = (
        (b_row - a_row) and ((b_row - a_row) // abs(b_row - a_row)),
        (b_col - a_col) and ((b_col - a_col) // abs(b_col - a_col)),
    )
    for name, delta in DIRECTIONS.items():
        if delta == (d[0] or 0, d[1] or 0):
            return name
    raise ValueError("cards are not adjacent along a straight line")

def entry_edges(origin: int, target: int, rows: int, cols: int) -> tuple[str, ...]:
    """Edges of the target card that fire from origin enters through.

    For a straight line of fire the target is entered through the side facing
    origin. For a diagonal, both edges of the corner are entered. Returns an
    empty tuple when origin and target are the same card or not in line.
    """
    if origin == target:
        return ()
    path = los_path(origin, target, rows, cols)
    if path is None or len(path) < 2:
        return ()
    direction = _direction_between(origin, path[1], rows, cols)
    return _edges_for(direction, leaving=False)


def entry_is_dark(colours: list[str], edges: tuple[str, ...]) -> bool:
    """True if any entry edge of a card has a non-white (dark or black) border."""
    return any(colours[_BORDER_INDEX[edge]] != "white" for edge in edges)


def board_los(cards: list[str], rows: int, cols: int, origin: int, target: int, limited: bool = False) -> bool:
    """LOS between two positions on a board whose cells are terrain card ids."""
    from app.games.fields_of_fire.terrain import get_card

    def borders(position: int) -> list[str]:
        card = get_card(cards[position]) if 0 <= position < len(cards) else None
        return list((card or {}).get("borders") or ["white"] * 4)

    return has_los(origin, target, rows, cols, borders, limited=limited)
