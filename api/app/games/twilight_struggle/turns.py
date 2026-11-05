"""Turn-structure helpers grounded in Twilight Struggle 2nd Edition rules."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
import random
from typing import Any

from app.core.rng import create_rng, serialize_rng
from app.games.twilight_struggle.space_race import EIGHT_ROUNDS_BOX, has_space_ability

FACTIONS = ("us", "ussr")


def action_round_limit(turn: int, extra_rounds: int = 0) -> int:
    """Return baseline action rounds per faction; event bonuses are explicit."""
    if not isinstance(turn, int) or not 1 <= turn <= 10:
        raise ValueError("turn must be between 1 and 10")
    if not isinstance(extra_rounds, int) or extra_rounds < 0:
        raise ValueError("extra_rounds must be a non-negative integer")
    return (6 if turn <= 3 else 7) + extra_rounds


def faction_action_limit(game_data: dict[str, Any], faction: str) -> int:
    """Action rounds a faction may take this turn, including turn-scoped event allowances."""
    turn = game_data.get("turn")
    limit = action_round_limit(turn, game_data.get("extra_action_rounds", 0))
    # North Sea Oil (86): the US may play up to 8 cards this turn.
    north_sea_oil = (game_data.get("persistent_events") or {}).get("north_sea_oil")
    if faction == "us" and isinstance(north_sea_oil, dict) and north_sea_oil.get("expires_turn") == turn:
        limit = max(limit, 8)
    # Space Station (Space Race box 8): the first faction there may take 8 action rounds per turn.
    if has_space_ability(game_data, faction, EIGHT_ROUNDS_BOX):
        limit = max(limit, 8)
    return limit


def faction_can_act(game_data: dict[str, Any], faction: str) -> bool:
    """A faction can take another action round only while under its limit and holding a card.

    A faction whose hand is empty has nothing to play and is finished for the turn (events such as
    Terrorism or Missile Envy can empty a hand before the limit is reached). Under Quagmire/Bear Trap,
    a faction marked scoring-only with no scoring card is likewise unable to take another action.
    """
    taken = (game_data.get("actions_taken") or {}).get(faction, 0)
    hand = (game_data.get("hands") or {}).get(faction) or []
    if taken >= faction_action_limit(game_data, faction) or not hand:
        return False
    restriction = (game_data.get("persistent_events") or {}).get("action_restriction")
    if isinstance(restriction, dict) and restriction.get("faction") == faction and restriction.get("scoring_only"):
        return any(card.get("scoring") for card in hand)
    return True


def hand_limit(turn: int) -> int:
    """Return the regular hand limit, excluding the China Card."""
    if not isinstance(turn, int) or not 1 <= turn <= 10:
        raise ValueError("turn must be between 1 and 10")
    return 8 if turn <= 3 else 9


def cards_entering_era(turn: int) -> int | None:
    """Return era insertion point: 1 Early, 2 Mid, 3 Late; None otherwise."""
    if turn == 1:
        return 1
    if turn == 4:
        return 2
    if turn == 8:
        return 3
    if isinstance(turn, int) and 1 <= turn <= 10:
        return None
    raise ValueError("turn must be between 1 and 10")


def start_turn_tracks(game_data: dict[str, Any], new_turn: int) -> dict[str, Any]:
    """Apply the start-of-turn track changes without mutating the source state."""
    if not isinstance(new_turn, int) or not 1 <= new_turn <= 10:
        raise ValueError("new_turn must be between 1 and 10")
    state = dict(game_data)
    tracks = dict(game_data.get("tracks", {}))
    defcon = tracks.get("defcon", 5)
    if not isinstance(defcon, int) or not 1 <= defcon <= 5:
        raise ValueError("DEFCON must be between 1 and 5")
    tracks["defcon"] = min(5, defcon + 1)
    state["tracks"] = tracks
    state["turn"] = new_turn
    state["action_round"] = 0
    state["actions_taken"] = {faction: 0 for faction in FACTIONS}
    state["current_player"] = "ussr"
    player_by_faction = game_data.get("player_by_faction")
    if player_by_faction is not None:
        if not isinstance(player_by_faction, dict) or not isinstance(player_by_faction.get("ussr"), str):
            raise ValueError("player_by_faction must map each faction to a player id")
        if not isinstance(player_by_faction.get("us"), str):
            raise ValueError("player_by_faction must map each faction to a player id")
        state["current_player"] = player_by_faction["ussr"]
    state["current_phase"] = "deal"
    return state


def record_action(game_data: dict[str, Any], faction: str) -> dict[str, Any]:
    """Increment a faction's action count and advance the round marker."""
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    state = dict(game_data)
    counts = dict(game_data.get("actions_taken", {f: 0 for f in FACTIONS}))
    counts[faction] = counts.get(faction, 0) + 1
    state["actions_taken"] = counts
    state["action_round"] = max(counts.values())
    return state


def initialize_card_deal(
    early_cards: list[dict[str, Any]],
    rng_seed: int,
    rng_state_json: str | None = None,
) -> dict[str, Any]:
    """Shuffle an Early War card catalog and deal eight cards to each faction.

    Card records are copied and must include stable ``id``, integer ``era``
    (1=Early), and boolean ``scoring`` metadata. Card event definitions are
    intentionally not interpreted here.
    """
    if len(early_cards) < 16:
        raise ValueError("At least 16 Early War cards are required for the opening deal")
    ids = [card.get("id") for card in early_cards]
    if any(card_id is None for card_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Early War cards must have unique non-null ids")
    if any(card.get("era") != 1 for card in early_cards):
        raise ValueError("Opening deck may contain only Early War cards")
    deck = deepcopy(early_cards)
    rng = create_rng(rng_seed, rng_state_json)
    rng.shuffle(deck)
    return {
        "hands": {"ussr": deck[:8], "us": deck[8:16]},
        "draw_pile": deck[16:],
        "discard_pile": [],
        "removed_cards": [],
        "rng_seed": rng_seed,
        "rng_state_json": serialize_rng(rng),
        "actions_taken": {"us": 0, "ussr": 0},
    }


def deal_to_hand_limit(
    game_data: dict[str, Any],
    turn: int,
    rng: random.Random,
) -> dict[str, Any]:
    """Deal each player up to the turn's hand size, reshuffling discards as needed.

    The caller inserts new-era cards before calling this at turns 4 and 8; the
    insertion shuffle must exclude the discard pile per the rulebook.
    """
    state = deepcopy(game_data)
    limit = hand_limit(turn)
    deck = state.setdefault("draw_pile", [])
    discard = state.setdefault("discard_pile", [])
    hands = state.setdefault("hands", {"us": [], "ussr": []})
    factions = ("ussr", "us")
    while any(len(hands.setdefault(faction, [])) < limit for faction in factions):
        dealt_this_pass = False
        for faction in factions:
            if len(hands[faction]) >= limit:
                continue
            if not deck:
                if not discard:
                    continue
                deck.extend(discard)
                discard.clear()
                rng.shuffle(deck)
            if not deck:
                continue
            hands[faction].append(deck.pop())
            dealt_this_pass = True
        if not dealt_this_pass:
            break
    state["rng_state_json"] = serialize_rng(rng)
    return state


def insert_era_cards(
    game_data: dict[str, Any],
    turn: int,
    new_era_cards: list[dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    """Add Mid/Late War cards to the draw pile without moving discards into it."""
    expected_era = cards_entering_era(turn)
    if expected_era not in {2, 3}:
        raise ValueError("Era cards may only be inserted at the start of turns 4 or 8")
    if any(card.get("era") != expected_era for card in new_era_cards):
        raise ValueError(f"Expected era {expected_era} card definitions")
    if expected_era in game_data.get("era_inserted", []):
        raise ValueError(f"Era {expected_era} cards have already been inserted")
    state = deepcopy(game_data)
    state.setdefault("draw_pile", []).extend(deepcopy(new_era_cards))
    rng.shuffle(state["draw_pile"])
    state["era_inserted"] = sorted(set(state.get("era_inserted", [])) | {expected_era})
    state["rng_state_json"] = serialize_rng(rng)
    return state
