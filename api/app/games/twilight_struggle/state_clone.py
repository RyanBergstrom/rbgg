"""Purpose-built state clone for Twilight Struggle ``game_data``.

``copy.deepcopy`` is generic and slow: it walks every card record in every pile
on each copy, and the engine copies state about 14 times per move. This clone
exploits the layout instead:

* ``countries`` is ``{name: {us, ussr}}``: copied as dict-of-dicts.
* Card piles and hands are lists of card records. Cards are immutable in this
  engine (they only move between piles and are never edited in place), so the
  records are shared and only the lists are copied.
* Every other key is deep-copied. That keeps the clone safe by default: an
  unrecognized or newly added key is never shared by accident.

Contract: the returned state is independent of the input for every mutation the
engine performs (editing countries, tracks, flags, and moving cards between
piles). The one sharing is the card records themselves; do not edit a card
dict in place. ``tests/test_twilight_struggle_clone.py`` enforces equivalence
with ``deepcopy`` and the no-in-place-card-edits rule.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_CARD_LISTS = ("draw_pile", "discard_pile", "removed_cards")
_ATOMS = (str, int, float, bool, type(None))


def _copy_plain(value: Any) -> Any:
    """Copy JSON-like data (dict/list/scalars) without deepcopy's memo bookkeeping.

    Game state is plain data with no shared references or cycles, so a memo table
    is wasted work. Any other type (set, tuple, custom object) falls back to
    ``deepcopy`` so nothing unexpected is ever shared.
    """
    kind = type(value)
    if kind in _ATOMS:
        return value
    if kind is dict:
        return {key: _copy_plain(item) for key, item in value.items()}
    if kind is list:
        return [_copy_plain(item) for item in value]
    return deepcopy(value)


def clone_state(game_data: dict[str, Any]) -> dict[str, Any]:
    """Return an independent copy of ``game_data`` that shares only immutable card records."""
    result: dict[str, Any] = {}
    for key, value in game_data.items():
        if key == "countries" and isinstance(value, dict):
            result[key] = {name: dict(entry) if isinstance(entry, dict) else _copy_plain(entry) for name, entry in value.items()}
        elif key in _CARD_LISTS and isinstance(value, list):
            result[key] = list(value)
        elif key == "hands" and isinstance(value, dict):
            result[key] = {side: list(cards) if isinstance(cards, list) else _copy_plain(cards) for side, cards in value.items()}
        else:
            result[key] = _copy_plain(value)
    return result


def clone_envelope(state: dict[str, Any]) -> dict[str, Any]:
    """Copy a validator state envelope (``game_data`` plus players and RNG fields)."""
    result: dict[str, Any] = {}
    for key, value in state.items():
        if key == "game_data" and isinstance(value, dict):
            result[key] = clone_state(value)
        else:
            result[key] = _copy_plain(value)
    return result


# Keys that identify a dict as a Twilight Struggle game_data (or validator envelope).
_GAME_DATA_MARKERS = ("countries", "hands", "tracks")


def fast_copy(value: Any) -> Any:
    """Drop-in for ``copy.deepcopy`` in the engine modules.

    A whole ``game_data`` (or validator envelope) is cloned with the layout-aware
    clone; anything else (a single card, a placement list, an action payload) gets
    a real ``deepcopy``. Detection is by shape, so a copy of the wrong kind of
    object can never be silently shared.
    """
    if isinstance(value, dict):
        if "game_data" in value and isinstance(value["game_data"], dict):
            return clone_envelope(value)
        if all(marker in value for marker in _GAME_DATA_MARKERS):
            return clone_state(value)
    return deepcopy(value)
