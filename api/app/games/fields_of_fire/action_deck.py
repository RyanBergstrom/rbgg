"""Fields of Fire Action Deck mechanics (rulebook 1.2.2, 1.2.7, 2.2.3).

The deck is 50 Action cards (A01-A50) plus one reshuffle card. Hint cards are
not part of the deck. All state is plain JSON-serialisable dicts so it can be
stored in ``game_data``.

Rules implemented here:
- A draw always takes the full requested number of cards, even if a result
  is reached earlier (2.2.3).
- If the reshuffle card is reached during a draw, the draw is completed and
  then every card (including the reshuffle card) is reshuffled. The reshuffle
  card does not count as one of the required draws.

Randomness is seeded so games are reproducible. Tests and debugging may force
the next draws with ``force_next``; forced cards are still logged.
"""
from __future__ import annotations

import json
import os
import random
from typing import Any

_CARDS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs", "fof", "cards-final.json")
_RESHUFFLE_ID = "FOF-ACTION-RESHUFFLE-CARD"


def load_action_cards() -> dict[str, dict[str, Any]]:
    """Return reviewed Action cards keyed by card id, from cards-final.json."""
    with open(os.path.normpath(_CARDS_PATH), encoding="utf-8") as f:
        cards = json.load(f)
    return {c["id"]: c for c in cards if c.get("card_type") == "action"}


_ACTION_CARDS = load_action_cards()
RESHUFFLE_CARD = _RESHUFFLE_ID
ACTION_CARD_IDS = sorted(
    cid for cid, c in _ACTION_CARDS.items()
    if cid != _RESHUFFLE_ID and c.get("action_details", {}).get("card_number")
)


def get_action_card(card_id: str) -> dict[str, Any]:
    """Return the cards-final record for an Action card id."""
    return _ACTION_CARDS[card_id]


def new_action_deck(seed: int = 0) -> dict[str, Any]:
    """Return a freshly shuffled Action Deck state."""
    deck: dict[str, Any] = {
        "seed": seed,
        "shuffle_count": 0,
        "draw_pile": list(ACTION_CARD_IDS) + [RESHUFFLE_CARD],
        "discard": [],
        "forced": [],
        "log": [],
    }
    _shuffle(deck)
    return deck


def _shuffle(deck: dict[str, Any]) -> None:
    cards = deck["draw_pile"] + deck["discard"]
    deck["discard"] = []
    rng = random.Random(f"{deck['seed']}:{deck['shuffle_count']}")
    rng.shuffle(cards)
    deck["draw_pile"] = cards
    deck["shuffle_count"] += 1


def force_next(deck: dict[str, Any], card_ids: list[str]) -> None:
    """Queue card ids to be drawn next, in order. For tests and debugging."""
    for card_id in card_ids:
        if card_id != RESHUFFLE_CARD and card_id not in ACTION_CARD_IDS:
            raise ValueError(f"unknown action card: {card_id}")
    deck["forced"].extend(card_ids)


def draw(deck: dict[str, Any], count: int, reason: str = "") -> list[str]:
    """Draw ``count`` Action cards, applying the reshuffle rule.

    Returns the drawn card ids (never the reshuffle card). Every draw is
    appended to ``deck["log"]``.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    drawn: list[str] = []
    reshuffle_pending = False
    while len(drawn) < count:
        card = _take_top(deck)
        if card == RESHUFFLE_CARD:
            reshuffle_pending = True
            continue
        drawn.append(card)
        deck["discard"].append(card)
    if reshuffle_pending:
        # Reshuffle only after the required draws are complete.
        deck["discard"].append(RESHUFFLE_CARD)
        _shuffle(deck)
    deck["log"].append({"reason": reason, "cards": list(drawn), "reshuffled": reshuffle_pending})
    return drawn


def _take_top(deck: dict[str, Any]) -> str:
    if deck["forced"]:
        forced = deck["forced"].pop(0)
        if forced in deck["draw_pile"]:
            deck["draw_pile"].remove(forced)
        elif forced in deck["discard"]:
            deck["discard"].remove(forced)
        return forced
    if not deck["draw_pile"]:
        _shuffle(deck)
    return deck["draw_pile"].pop(0)
