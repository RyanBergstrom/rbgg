"""Lost Cities validator — implements LegalMoveValidator.

Lost Cities is a 2-player card game by Reiner Knizia.
- 60 cards: 5 colors (blue, yellow, red, white, green) × (3 investment + 9 numbered 2-10)
- Each player starts with 8 cards
- On turn: play 1 card to expedition or discard, then draw 1 card
- Expeditions must be ascending; investments must come first
- Game ends when draw pile empty; score expeditions
"""

from __future__ import annotations

import random
from typing import Any

from app.core.legal_move_interface import LegalMoveValidator
from app.core.mcts import MCTSConfig
from app.core.rng import create_rng, serialize_rng

# Color constants
COLORS = ["blue", "yellow", "red", "white", "green"]
COLOR_SHORT = {"blue": "b", "yellow": "y", "red": "r", "white": "w", "green": "g"}
SHORT_TO_COLOR = {v: k for k, v in COLOR_SHORT.items()}

# Card values
INVESTMENT = "i"
NUMBERS = list(range(2, 11))  # 2-10

# Card strings are immutable and drawn from a fixed 60-card vocabulary. Cache
# their decoded metadata so the training hot loop does not repeatedly split
# strings and translate color codes.
CARD_METADATA = {
    f"{short}_{value}": (color, str(value))
    for color in COLORS
    for short in [COLOR_SHORT[color]]
    for value in [INVESTMENT, *NUMBERS]
}

# Total cards per color: 3 investment + 9 numbered = 12
# 5 colors × 12 = 60 cards


def create_deck(rng: random.Random | None = None) -> list[str]:
    """Create a shuffled deck of 60 cards."""
    deck = []
    for color in COLORS:
        short = COLOR_SHORT[color]
        for _ in range(3):
            deck.append(f"{short}_{INVESTMENT}")
        for num in NUMBERS:
            deck.append(f"{short}_{num}")
    (rng or random.Random()).shuffle(deck)
    return deck


def parse_card(card: str) -> tuple[str, str]:
    """Parse card string into (color_short, value)."""
    parts = card.split("_", 1)
    return parts[0], parts[1]


def card_color(card: str) -> str:
    """Get full color name from card."""
    return CARD_METADATA[card][0]


def card_value(card: str) -> str:
    """Get value from card (i or 2-10)."""
    return CARD_METADATA[card][1]


def is_investment(card: str) -> bool:
    """Check if card is an investment card."""
    return card_value(card) == INVESTMENT


def is_numbered(card: str) -> bool:
    """Check if card is a numbered card (2-10)."""
    val = card_value(card)
    return val.isdigit()


def card_number(card: str) -> int | None:
    """Get numeric value of numbered card, None for investment."""
    val = card_value(card)
    if val.isdigit():
        return int(val)
    return None


def _opponent(player_id: str) -> str:
    return "player_2" if player_id == "player_1" else "player_1"


def _initial_game_data(
    rng_seed: int = 42,
    rng_state_json: str | None = None,
) -> dict[str, Any]:
    """Create initial game state for a new round."""
    rng = create_rng(rng_seed, rng_state_json)
    deck = create_deck(rng)
    return {
        "player_hands": {
            "player_1": deck[:8],
            "player_2": deck[8:16],
        },
        "expeditions": {
            "player_1": {c: [] for c in COLORS},
            "player_2": {c: [] for c in COLORS},
        },
        "discard_piles": {c: [] for c in COLORS},
        "draw_pile": deck[16:],
        "current_phase": "play_a_card",
        "current_player": "player_1",
        "last_discarded": None,  # {"player_id": "", "card": "", "color": ""}
        "round": 1,
        "scores": {"player_1": 0, "player_2": 0},
        "round_summaries": [],
        "last_round_summary": None,
        "game_over": False,
        "round_over": False,
        "pending_draw": False,  # True after playing a card, before drawing
        "_rng_state_json": serialize_rng(rng),
    }


def _can_play_to_expedition(expedition: list[str], card: str) -> bool:
    """Check if a card can be legally played to an expedition."""
    if not expedition:
        # Empty expedition: any card can start it
        return True

    if is_investment(card):
        # Investment cards can only be played on empty or on top of another investment
        return all(is_investment(c) for c in expedition)

    # Numbered card: must be higher than last numbered card in the expedition
    last_num = None
    for c in reversed(expedition):
        if is_numbered(c):
            last_num = card_number(c)
            break

    if last_num is None:
        # No numbered cards yet (only investments), any numbered card starts the sequence
        return True

    return card_number(card) > last_num


def _calculate_expedition_score(cards: list[str]) -> int:
    """Calculate score for a single expedition."""
    if not cards:
        return 0

    investment_count = sum(1 for c in cards if is_investment(c))
    numbered_cards = [c for c in cards if is_numbered(c)]

    if not numbered_cards:
        # Investment only: -20 * multiplier
        base = -20
    else:
        total = sum(card_number(c) for c in numbered_cards)
        base = total - 20

    multiplier = 1 + investment_count
    score = base * multiplier

    # Length bonus: 8+ cards total
    if len(cards) >= 8:
        score += 20

    return score


def _calculate_player_score(expeditions: dict[str, list[str]]) -> int:
    """Calculate total score for a player."""
    return sum(_calculate_expedition_score(expeditions[color]) for color in COLORS)


def _build_expedition_score_breakdown(cards: list[str]) -> dict[str, Any]:
    """Return a structured score breakdown for one expedition."""
    investment_count = sum(1 for card in cards if is_investment(card))
    numbered_sum = sum(card_number(card) or 0 for card in cards if is_numbered(card))
    started = bool(cards)
    base_score = (numbered_sum - 20) if started else 0
    multiplier = (1 + investment_count) if started else 1
    bonus = 20 if len(cards) >= 8 else 0
    return {
        "cards": list(cards),
        "started": started,
        "investment_count": investment_count,
        "numbered_sum": numbered_sum,
        "base_score": base_score,
        "multiplier": multiplier,
        "bonus": bonus,
        "score": _calculate_expedition_score(cards),
    }


def _build_score_breakdown(game_data: dict[str, Any]) -> dict[str, Any]:
    """Return banked and current-round score details for both players."""
    expeditions = game_data.get("expeditions", {})
    banked_scores = game_data.get("scores", {})
    players: dict[str, Any] = {}

    for player_id in ("player_1", "player_2"):
        expedition_breakdown = {
            color: _build_expedition_score_breakdown(expeditions.get(player_id, {}).get(color, []))
            for color in COLORS
        }
        current_round_score = sum(details["score"] for details in expedition_breakdown.values())
        banked_score = int(banked_scores.get(player_id, 0))
        players[player_id] = {
            "banked_score": banked_score,
            "current_round_score": current_round_score,
            "overall_total": banked_score + current_round_score,
            "expeditions": expedition_breakdown,
        }

    return {
        "players": players,
        "round": game_data.get("round", 1),
        "game_over": game_data.get("game_over", False),
        "round_over": game_data.get("round_over", False),
    }


def _build_round_summary(game_data: dict[str, Any], round_number: int) -> dict[str, Any]:
    """Capture the just-finished round before expeditions are reset."""
    score_breakdown = _build_score_breakdown(game_data)
    starting_scores = {
        player_id: score_breakdown["players"][player_id]["banked_score"]
        for player_id in ("player_1", "player_2")
    }
    round_scores = {
        player_id: score_breakdown["players"][player_id]["current_round_score"]
        for player_id in ("player_1", "player_2")
    }
    ending_scores = {
        player_id: starting_scores[player_id] + round_scores[player_id]
        for player_id in ("player_1", "player_2")
    }
    players = {
        player_id: {
            "banked_score_before_round": starting_scores[player_id],
            "current_round_score": round_scores[player_id],
            "ending_total": ending_scores[player_id],
            "expeditions": score_breakdown["players"][player_id]["expeditions"],
        }
        for player_id in ("player_1", "player_2")
    }
    return {
        "round": round_number,
        "starting_scores": starting_scores,
        "round_scores": round_scores,
        "ending_scores": ending_scores,
        "players": players,
    }


def _game_turn_number(game_data: dict[str, Any]) -> int:
    """Compute the current turn number from game state.

    Turn number = max cards played across all expeditions for any player.
    """
    expeditions = game_data.get("expeditions", {})
    max_played = 0
    for pid in ("player_1", "player_2"):
        player_exp = expeditions.get(pid, {})
        total = sum(len(cards) for cards in player_exp.values())
        max_played = max(max_played, total)
    return max_played


def _get_legal_plays(state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
    """Get all legal plays (expedition or discard) for the current player."""
    game_data = state.get("game_data", {})
    hand = game_data.get("player_hands", {}).get(player_id, [])
    expeditions = game_data.get("expeditions", {}).get(player_id, {})

    moves = []
    for idx, card in enumerate(hand):
        color = card_color(card)

        # Option 1: Play to expedition
        if _can_play_to_expedition(expeditions[color], card):
            moves.append({
                "move_id": f"play_exp_{card}_{idx}",
                "type": "play_expedition",
                "card": card,
                "color": color,
                "hand_index": idx,
                "player_id": player_id,
            })

        # Option 2: Discard (always legal)
        moves.append({
            "move_id": f"discard_{card}_{idx}",
            "type": "discard",
            "card": card,
            "color": color,
            "hand_index": idx,
            "player_id": player_id,
        })

    return moves


def _get_legal_draws(state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
    """Get all legal draw sources for the current player."""
    game_data = state.get("game_data", {})
    draw_pile = game_data.get("draw_pile", [])
    discard_piles = game_data.get("discard_piles", {})
    last_discarded = game_data.get("last_discarded")

    moves = []

    # Draw from draw pile
    if draw_pile:
        moves.append({
            "move_id": "draw_draw_pile",
            "type": "draw",
            "source": "draw_pile",
            "player_id": player_id,
        })

    # Draw from discard piles (top card only, not the one just discarded)
    for color in COLORS:
        pile = discard_piles.get(color, [])
        if pile:
            top_card = pile[-1]
            if last_discarded and last_discarded["player_id"] == player_id and last_discarded["card"] == top_card:
                continue  # Cannot draw the card you just discarded
            moves.append({
                "move_id": f"draw_{color}_discard",
                "type": "draw",
                "source": f"{color}_discard",
                "player_id": player_id,
            })

    return moves


def _copy_game_data_for_transition(game_data: dict[str, Any]) -> dict[str, Any]:
    """Copy only mutable Lost Cities containers touched by a move.

    This preserves the validator's copy-on-transition contract without paying
    for a recursive deepcopy of every scalar and card string on each training
    step. Unknown extension fields are retained by reference and must therefore
    be immutable or copied by the extension before mutation.
    """
    copied = dict(game_data)
    for key in ("player_hands", "expeditions", "discard_piles", "scores"):
        value = game_data.get(key)
        if isinstance(value, dict):
            copied[key] = dict(value)

    hands = copied.get("player_hands")
    if isinstance(hands, dict):
        copied["player_hands"] = {
            player_id: list(cards) if isinstance(cards, list) else cards
            for player_id, cards in hands.items()
        }

    for key in ("expeditions", "discard_piles"):
        containers = copied.get(key)
        if not isinstance(containers, dict):
            continue
        copied[key] = {
            owner_or_color: (
                {
                    color: list(cards) if isinstance(cards, list) else cards
                    for color, cards in values.items()
                }
                if key == "expeditions" and isinstance(values, dict)
                else list(values) if isinstance(values, list) else values
            )
            for owner_or_color, values in containers.items()
        }

    if isinstance(copied.get("scores"), dict):
        copied["scores"] = dict(copied["scores"])
    if isinstance(copied.get("last_discarded"), dict):
        copied["last_discarded"] = dict(copied["last_discarded"])
    return copied


def _count_unseen_cards(game_data: dict[str, Any], color: str, exclude_hand: list[str] | None = None) -> int:
    """Count cards of a color not in any expedition, the given hand, or discard piles."""
    expeditions = game_data.get("expeditions", {})
    discard_piles = game_data.get("discard_piles", {})
    exclude_hand = exclude_hand or []

    in_expeditions = sum(
        1 for pid in ("player_1", "player_2")
        for c in expeditions.get(pid, {}).get(color, [])
    )
    in_discard = len(discard_piles.get(color, []))
    in_hand = sum(1 for c in exclude_hand if card_color(c) == color)

    total = 3 + 9  # 3 investment + 9 numbered per color
    return total - in_expeditions - in_discard - in_hand


def _expedition_score_after_playing(
    expedition: list[str], card: str, hand: list[str]
) -> int:
    """Score for committing to this color: existing expedition + all playable hand cards + this card."""
    cards = list(expedition)
    if card not in cards:
        cards.append(card)
    color = card_color(card)
    for c in hand:
        if c != card and card_color(c) == color and _can_play_to_expedition(cards, c):
            cards.append(c)
    return _calculate_expedition_score(cards)


def _compute_play_score(
    expedition: list[str], card: str, hand: list[str], unseen: int, draws_left: int,
    total_remaining: int = 0,
) -> float:
    """Score for a play_expedition move: base + upside - risk."""
    # Guaranteed: best expedition if we commit all playable hand cards
    guaranteed = _expedition_score_after_playing(expedition, card, hand)

    # Upside: expected value from cards still out there (deck only, not hand)
    color = card_color(card)
    upside = 0.0
    if unseen > 0:
        upside_sum = 0
        # Start from the full committed expedition (card + all playable hand cards)
        test_cards = list(expedition)
        if card not in test_cards:
            test_cards.append(card)
        for c in hand:
            if c != card and card_color(c) == color and _can_play_to_expedition(test_cards, c):
                test_cards.append(c)
        # Now add deck cards and sum their marginals
        for num in NUMBERS:
            test_card = f"{COLOR_SHORT[color]}_{num}"
            if _can_play_to_expedition(test_cards, test_card):
                test_cards.append(test_card)
                upside_sum += _calculate_expedition_score(test_cards) - _calculate_expedition_score(test_cards[:-1])
        # Expected fraction of these cards we'll draw:
        # - P(specific card is in draw pile) ≈ draws_left / total_remaining
        # - We draw ~half the draw pile (alternating turns)
        # So expected draws of this color ≈ unseen * draws_left / total_remaining * 0.5
        # Scale upside by expected_drawn / unseen
        if total_remaining > 0:
            upside = upside_sum * draws_left / (2 * total_remaining)
        else:
            upside = upside_sum * (draws_left / unseen) if unseen > 0 else 0.0

    # Risk: penalty for negative expeditions where we might not recover
    if guaranteed >= 0:
        risk = 0.0
    else:
        avg_value = sum(num for num in NUMBERS) / len(NUMBERS)
        investment_count = sum(1 for c in expedition if is_investment(c)) + (1 if is_investment(card) else 0)
        multiplier = 1 + investment_count
        cards_to_breakeven = int((-guaranteed / (avg_value * multiplier)) + 1)
        cards_to_breakeven = max(1, min(cards_to_breakeven, unseen))
        p_not_drawn = (1 - unseen / (30 + unseen)) ** cards_to_breakeven
        risk = abs(guaranteed) * p_not_drawn

    return guaranteed + upside - risk


def compute_play_score_v2(
    card: str,
    hand: list[str],
    game_data: dict,
    player_id: str,
) -> float:
    """Score a play_expedition move: guaranteed score + expected value from draws.

    Args:
        card: The card being scored (e.g., "r_5").
        hand: Current player's full hand.
        game_data: Full game state with expeditions, discard_piles, etc.
        player_id: The player whose perspective is being scored.

    Returns:
        float: Expected score for playing this card.
    """
    color = card_color(card)

    expeditions = game_data.get("expeditions", {})
    discard_piles = game_data.get("discard_piles", {})

    opponent_id = _opponent(player_id)
    my_expedition = expeditions.get(player_id, {}).get(color, [])
    opponent_expedition = expeditions.get(opponent_id, {}).get(color, [])
    my_discard = discard_piles.get(color, [])

    # All 12 cards of this color in order: 3 investments, then 2-10
    all_color_cards = []
    for _ in range(3):
        all_color_cards.append(f"{COLOR_SHORT[color]}_i")
    for num in NUMBERS:
        all_color_cards.append(f"{COLOR_SHORT[color]}_{num}")

    # Determine where to start counting based on the card being scored.
    # Only cards >= the scored card (sequentially playable after it) count.
    if is_investment(card):
        # Scoring an investment: count all investments in hand + this one
        start_index = 0
        inv_in_hand = sum(1 for c in hand if card_color(c) == color and is_investment(c))
        inv_in_expedition = sum(1 for c in my_expedition if is_investment(c))
        inv_count = min(inv_in_hand + inv_in_expedition, 3)
        guaranteed_investments = [f"{COLOR_SHORT[color]}_i"] * inv_count
    else:
        # Scoring a numbered card: investments must be played first, don't count them
        start_index = 3 + (card_number(card) - 2)
        guaranteed_investments = []

    # Partition cards into guaranteed (in hand/expedition) and to draw (in deck).
    # Sequential constraint: investments are always playable, but numbered cards
    # must be in ascending order. Any numbered card lower than one we already have
    # is unplayable and any drawable card must be higher than our highest guaranteed.
    guaranteed_cards = list(guaranteed_investments)

    # Add the card being played to guaranteed_cards (it's being played now)
    # For investments, it's already in guaranteed_investments, so skip to avoid duplicate
    if not is_investment(card):
        guaranteed_cards.append(card)

    cards_to_draw = []

    # Pre-compute: lowest numbered card we already have sets the floor.
    # Anything below it is unplayable.
    numbered_in_hand_or_exp = [
        card_number(c) for c in hand + my_expedition
        if card_color(c) == color and is_numbered(c)
    ]
    highest_numbered_guaranteed = max(numbered_in_hand_or_exp) if numbered_in_hand_or_exp else 0

    for c in all_color_cards[start_index:]:
        # Skip cards on opponent's expedition or in any discard pile
        if c in opponent_expedition or c in my_discard:
            continue

        # Skip investment cards — handled above when scoring investments
        if is_investment(c):
            continue

        # Skip the card being played — already added to guaranteed_cards
        if c == card:
            continue

        if c in my_expedition or c in hand:
            guaranteed_cards.append(c)
        else:
            # Only count as drawable if higher than anything we already have.
            # Cards lower than a guaranteed numbered card can never be played.
            if is_numbered(c) and card_number(c) > highest_numbered_guaranteed:
                cards_to_draw.append(c)

    # --- Score 1: guaranteed expedition score from cards we have ---
    guaranteed_score = _calculate_expedition_score(guaranteed_cards)

    # --- Score 2: expected value from cards we need to draw ---
    # Sum the numbered values, apply investment multiplier, then 50%
    draw_sum = sum(card_number(c) for c in cards_to_draw if is_numbered(c))

    investment_count = sum(1 for c in guaranteed_cards if is_investment(c))
    multiplier = 1 + investment_count
    expected_value = draw_sum * multiplier * 0.5

    # --- 8-card bonus: +20 only if we have 8+ cards guaranteed ---
    total_cards = len(guaranteed_cards)
    bonus = 20.0 if total_cards >= 8 else 0.0

    # --- Penalty for killed cards ---
    # Numbered cards in hand lower than the scored card become unplayable.
    # E.g., playing yellow-8 with yellow-6 in hand kills the 6.
    # Multiply by 3 to heavily discourage killing cards.
    killed_penalty = 0
    if not is_investment(card):
        card_num = card_number(card)
        killed_penalty = sum(
            card_number(c) for c in hand
            if card_color(c) == color and is_numbered(c) and card_number(c) < card_num
        ) * 3

    # --- Penalty for wasted investments ---
    # Playing a numbered card first wastes the investment multiplier.
    # E.g., playing yellow-8 with yellow-i in hand wastes the i.
    wasted_inv_penalty = 0
    if not is_investment(card):
        inv_in_hand = sum(1 for c in hand if card_color(c) == color and is_investment(c))
        wasted_inv_penalty = inv_in_hand * 15

    return guaranteed_score + expected_value + bonus - killed_penalty - wasted_inv_penalty


class LostCitiesValidator(LegalMoveValidator):
    """Implements LegalMoveValidator for Lost Cities."""

    _mcts_init_args: tuple = ()


    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        game_data = state.get("game_data", {})
        player_id = move.get("player_id")
        move_type = move.get("type")

        if not player_id:
            return False

        # Check it's this player's turn
        current_player = game_data.get("current_player")
        if current_player != player_id:
            return False

        current_phase = game_data.get("current_phase")

        if current_phase == "play_a_card":
            if move_type not in ("play_expedition", "discard"):
                return False
            legal_plays = _get_legal_plays(state, player_id)
            # Match by move content (card, type, color) not move_id
            for legal in legal_plays:
                if (legal["type"] == move["type"] and
                    legal["card"] == move.get("card") and
                    legal["color"] == move.get("color")):
                    return True
            return False

        elif current_phase == "draw_a_card":
            if move_type != "draw":
                return False
            legal_draws = _get_legal_draws(state, player_id)
            for legal in legal_draws:
                if legal["source"] == move.get("source"):
                    return True
            return False

        return False


    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        game_data = state.get("game_data", {})
        current_player = game_data.get("current_player")
        current_phase = game_data.get("current_phase")

        if game_data.get("game_over"):
            return []

        if current_player != player_id:
            return []

        if current_phase == "play_a_card":
            return _get_legal_plays(state, player_id)
        elif current_phase == "draw_a_card":
            return _get_legal_draws(state, player_id)

        return []


    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        game_data = _copy_game_data_for_transition(state.get("game_data", {}))
        player_id = move.get("player_id")
        move_type = move.get("type")
        transition_rng_state = None

        if move_type == "play_expedition":
            card = move["card"]
            color = move["color"]
            hand_index = move["hand_index"]

            # Remove from hand
            hand = game_data["player_hands"][player_id]
            if hand_index < len(hand) and hand[hand_index] == card:
                hand.pop(hand_index)
            else:
                # Find by value if index shifted
                try:
                    hand.remove(card)
                except ValueError:
                    pass

            # Add to expedition
            game_data["expeditions"][player_id][color].append(card)

            # Switch to draw phase
            game_data["current_phase"] = "draw_a_card"
            game_data["pending_draw"] = True

        elif move_type == "discard":
            card = move["card"]
            color = move["color"]
            hand_index = move["hand_index"]

            # Remove from hand
            hand = game_data["player_hands"][player_id]
            if hand_index < len(hand) and hand[hand_index] == card:
                hand.pop(hand_index)
            else:
                try:
                    hand.remove(card)
                except ValueError:
                    pass

            # Add to discard pile
            game_data["discard_piles"][color].append(card)

            # Record last discarded (for draw restriction)
            game_data["last_discarded"] = {
                "player_id": player_id,
                "card": card,
                "color": color,
            }

            # Switch to draw phase
            game_data["current_phase"] = "draw_a_card"
            game_data["pending_draw"] = True

        elif move_type == "draw":
            source = move["source"]

            if source == "draw_pile":
                if game_data["draw_pile"]:
                    drawn = game_data["draw_pile"].pop(0)
                    game_data["player_hands"][player_id].append(drawn)

                    # Check for round end
                    if not game_data["draw_pile"]:
                        game_data["round_over"] = True

            else:  # draw from discard pile
                color = source.replace("_discard", "")
                if game_data["discard_piles"][color]:
                    drawn = game_data["discard_piles"][color].pop()
                    game_data["player_hands"][player_id].append(drawn)

            # Clear last_discarded after draw
            game_data["last_discarded"] = None
            game_data["pending_draw"] = False

            # Switch to next player's play phase
            game_data["current_player"] = _opponent(player_id)
            game_data["current_phase"] = "play_a_card"

            # Check for game end (after 3 rounds)
            if game_data.get("round_over"):
                round_number = int(game_data.get("round", 1))
                round_summary = _build_round_summary(game_data, round_number)
                # Score the round
                for pid in ["player_1", "player_2"]:
                    score = round_summary["round_scores"][pid]
                    game_data["scores"][pid] += score

                summaries = list(game_data.get("round_summaries", []))
                summaries.append(round_summary)
                game_data["round_summaries"] = summaries
                game_data["last_round_summary"] = round_summary

                game_data["round"] += 1

                if game_data["round"] > 3:
                    game_data["game_over"] = True
                else:
                    # Start new round
                    rng = create_rng(
                        state.get("rng_seed", 42),
                        state.get("rng_state_json", "{}"),
                    )
                    self._start_new_round(game_data, rng)
                    transition_rng_state = serialize_rng(rng)

        result = {"game_data": game_data}
        if transition_rng_state is not None:
            result["rng_state_json"] = transition_rng_state
        return result

    def _start_new_round(
        self, game_data: dict[str, Any], rng: random.Random | None = None
    ) -> None:
        """Reset for a new round, keeping cumulative scores."""
        deck = create_deck(rng)
        game_data["player_hands"] = {
            "player_1": deck[:8],
            "player_2": deck[8:16],
        }
        game_data["expeditions"] = {
            "player_1": {c: [] for c in COLORS},
            "player_2": {c: [] for c in COLORS},
        }
        game_data["discard_piles"] = {c: [] for c in COLORS}
        game_data["draw_pile"] = deck[16:]
        game_data["current_phase"] = "play_a_card"
        # Player with higher total score starts
        if game_data["scores"]["player_2"] > game_data["scores"]["player_1"]:
            game_data["current_player"] = "player_2"
        else:
            game_data["current_player"] = "player_1"
        game_data["last_discarded"] = None
        game_data["round_over"] = False
        game_data["pending_draw"] = False


    def check_win(self, state: dict[str, Any]) -> str | None:
        """Return the final outcome without mutating the supplied state.

        Completing a round is not a game win. Round scoring and setup for the
        next round happen in ``apply_move``; only ``game_over`` is terminal.
        Tied cumulative scores return the explicit ``draw`` outcome.
        """
        game_data = state.get("game_data", {})

        if game_data.get("game_over"):
            p1_score = game_data["scores"]["player_1"]
            p2_score = game_data["scores"]["player_2"]
            if p1_score > p2_score:
                return "player_1"
            elif p2_score > p1_score:
                return "player_2"
            return "draw"

        return None


    def recommend_ai_move(
        self, state: dict[str, Any], candidate_moves: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if not candidate_moves:
            return None

        game_data = state.get("game_data", {})
        current_phase = game_data.get("current_phase")

        if current_phase == "play_a_card":
            # Prefer playing to expedition over discarding
            expedition_moves = [m for m in candidate_moves if m["type"] == "play_expedition"]
            if expedition_moves:
                # Prefer higher numbered cards, then investments
                return max(expedition_moves, key=lambda m: (
                    0 if is_investment(m["card"]) else card_number(m["card"])
                ))
            # Must discard - prefer lowest value or investment we can't use
            discard_moves = [m for m in candidate_moves if m["type"] == "discard"]
            return min(discard_moves, key=lambda m: (
                100 if is_investment(m["card"]) else card_number(m["card"])
            ))

        elif current_phase == "draw_a_card":
            # Prefer draw pile (more cards), then discard piles with useful cards
            draw_pile_moves = [m for m in candidate_moves if m["source"] == "draw_pile"]
            if draw_pile_moves:
                return draw_pile_moves[0]
            # Otherwise take from discard if it matches our expeditions
            for move in candidate_moves:
                if move["source"].endswith("_discard"):
                    color = move["source"].replace("_discard", "")
                    # Check if we have expedition in this color or can start one
                    expeditions = game_data.get("expeditions", {}).get("player_2", {})
                    if expeditions.get(color) or True:  # Simple heuristic
                        return move
            return candidate_moves[0]

        return candidate_moves[0]

    def ai_config(self) -> MCTSConfig:
        """Return MCTS config for Lost Cities."""
        return MCTSConfig(
            iterations=300,
            exploration_constant=1.414,
            max_depth=500,
            workers=6,
        )

    def create_search_policy(self, _validator=None):
        from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
        return LostCitiesSearchPolicy(self)

    def stop_rollout(self, state: dict[str, Any], player_id: str) -> bool:
        """Stop the rollout when the draw pile is empty (single round)."""
        game_data = state.get("game_data", {})
        return not game_data.get("draw_pile")

    def filter_moves(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
        turn: int,
    ) -> list[dict[str, Any]]:
        """Filter moves based on game phase.

        Turns 1-5: Only play the lowest card of each color (investments always allowed).
        Turns 1-2: Additional restrictions on discards and draws.
        After turn 5: No filtering.
        """
        game_data = state.get("game_data", {})
        turn_number = _game_turn_number(game_data)

        hand = game_data.get("player_hands", {}).get(player_id, [])
        expeditions = game_data.get("expeditions", {}).get(player_id, {})

        filtered = []
        for m in moves:
            move_type = m.get("type")
            card = m.get("card", "")
            color = m.get("color", "")

            if move_type in ("play_expedition", "discard"):
                # Turns 1-5: Only play lowest card of each color
                if turn_number <= 5 and move_type == "play_expedition":
                    # Investments are always allowed
                    if not is_investment(card):
                        # Find all cards of this color in hand
                        same_color = [c for c in hand if card_color(c) == color]
                        same_color_investments = [c for c in same_color if is_investment(c)]
                        same_color_numbered = [c for c in same_color if is_numbered(c)]

                        # If you have investments of this color, must play them first
                        if same_color_investments:
                            continue

                        # If you have multiple numbered cards, only play the lowest
                        if same_color_numbered:
                            lowest = min(card_number(c) for c in same_color_numbered)
                            if card_number(card) != lowest:
                                continue

                # Turns 1-2: Never play 9 or 10
                if turn_number <= 2 and move_type == "play_expedition":
                    if is_numbered(card) and card_number(card) in (9, 10):
                        continue

                # Turns 1-2: Never discard if >3 of same color in hand
                if turn_number <= 2 and move_type == "discard":
                    same_color_count = sum(1 for c in hand if card_color(c) == color)
                    expedition = expeditions.get(color, [])
                    has_numbered_card = any(is_numbered(c) for c in expedition)
                    if same_color_count > 3 and not (
                        is_investment(card) and has_numbered_card
                    ):
                        continue

                    # Never discard investment if >1 of same color in hand
                    if is_investment(card):
                        if same_color_count > 1 and not has_numbered_card:
                            continue

            elif move_type == "draw":
                source = m.get("source", "")

                if source.endswith("_discard"):
                    draw_color = source.replace("_discard", "")

                    # Turns 1-2: Never draw discard of a color you have 0 of in hand
                    if turn_number <= 2:
                        hand_colors = {card_color(c) for c in hand}
                        if draw_color not in hand_colors:
                            continue

                    # Never draw an unplayable card
                    # Check if any card in the discard pile top matches
                    discard_pile = game_data.get("discard_piles", {}).get(draw_color, [])
                    if discard_pile:
                        top_card = discard_pile[-1]
                        if not _can_play_to_expedition(expeditions.get(draw_color, []), top_card):
                            continue

            filtered.append(m)

        return filtered

    def prior_moves(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
        turn: int,
    ) -> dict[str, float]:
        """Assign soft preference values to moves for MCTS expansion ordering."""
        game_data = state.get("game_data", {})
        turn_number = _game_turn_number(game_data)

        # After turn 2, pure MCTS — no priors
        if turn_number > 2:
            return {m.get("move_id", ""): 0.0 for m in moves}

        hand = game_data.get("player_hands", {}).get(player_id, [])
        expeditions = game_data.get("expeditions", {}).get(player_id, {})

        priors = {}
        for m in moves:
            move_type = m.get("type")
            card = m.get("card", "")
            color = m.get("color", "")
            prior = 0.0

            if move_type == "play_expedition":
                # +0.3 for playing investment cards (multiplier compounds)
                if is_investment(card):
                    prior += 0.3

                # +0.2 for extending existing expeditions (commitment bonus)
                elif expeditions.get(color):
                    prior += 0.2

                # +0.5 for playing lowest card when >3 of same color
                same_color = [c for c in hand if card_color(c) == color and is_numbered(c)]
                all_same_color = [c for c in hand if card_color(c) == color]
                if len(all_same_color) > 3:
                    if same_color and card_number(card) == min(card_number(c) for c in same_color):
                        prior += 0.5

            elif move_type == "discard":
                # +0.2 for discarding high cards (9/10) you can't use
                if is_numbered(card) and card_number(card) >= 9:
                    same_color = [c for c in hand if card_color(c) == color]
                    has_investment = any(is_investment(c) for c in same_color)
                    has_low_cards = any(
                        is_numbered(c) and card_number(c) < card_number(card)
                        for c in same_color
                    )
                    if not has_investment and not has_low_cards:
                        prior += 0.2

            elif move_type == "draw":
                source = m.get("source", "")
                # +0.1 for drawing from pile over discard (early game)
                if source == "draw_pile":
                    prior += 0.1

            priors[m.get("move_id", "")] = prior

        return priors

    def expansion_weights(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Return weights for expansion move selection.

        For play_expedition moves: score using heuristic, normalize to 0-1.
        For other moves: return 1.0 (always include).
        Moves with negative heuristic scores are excluded (weight 0).
        """
        game_data = state.get("game_data", {})
        hand = game_data.get("player_hands", {}).get(player_id, [])

        # Score play_expedition moves
        play_scores = {}
        for m in moves:
            if m.get("type") == "play_expedition":
                card = m.get("card", "")
                play_scores[m["move_id"]] = compute_play_score_v2(card, hand, game_data, player_id)

        # If no play moves, return all 1.0
        if not play_scores:
            return {m.get("move_id", ""): 1.0 for m in moves}

        # Normalize play scores to 0-1 range
        min_score = min(play_scores.values())
        max_score = max(play_scores.values())
        score_range = max_score - min_score

        weights = {}
        for m in moves:
            move_id = m.get("move_id", "")
            if m.get("type") == "play_expedition":
                raw = play_scores[move_id]
                # Exclude moves with very negative scores
                if raw < -10:
                    weights[move_id] = 0.0
                elif score_range > 0:
                    # Normalize to 0-1, with -10 mapping to 0
                    weights[move_id] = max(0.0, (raw + 10) / (score_range + 10))
                else:
                    weights[move_id] = 0.5
            else:
                weights[move_id] = 1.0

        return weights

    def score_moves(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Score each legal move for heuristic-weighted rollout selection.

        For play_expedition: guaranteed score + expected value from draws (v2).
        For discard: +10 if unplayable (frees hand slot), 0 otherwise.
        For draw: if can play drawn card, compute its expected value; else 0.
        """
        game_data = state.get("game_data", {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        discard_piles = game_data.get("discard_piles", {})

        scores = {}
        for m in moves:
            move_type = m.get("type")
            card = m.get("card", "")
            color = m.get("color", "")

            if move_type == "play_expedition":
                scores[m["move_id"]] = compute_play_score_v2(card, hand, game_data, player_id)

            elif move_type == "discard":
                can_play = False
                for c in COLORS:
                    if _can_play_to_expedition(expeditions.get(c, []), card):
                        can_play = True
                        break
                if not can_play:
                    scores[m["move_id"]] = 10.0
                else:
                    play_val = compute_play_score_v2(card, hand, game_data, player_id)
                    scores[m["move_id"]] = 0.5 if play_val > 0 else 0.0

            elif move_type == "draw":
                source = m.get("source", "")
                if source == "draw_pile":
                    scores[m["move_id"]] = 0.5
                else:
                    draw_color = source.replace("_discard", "")
                    pile = discard_piles.get(draw_color, [])
                    if pile:
                        top_card = pile[-1]
                        if _can_play_to_expedition(expeditions.get(draw_color, []), top_card):
                            unseen = _count_unseen_cards(game_data, draw_color, exclude_hand=hand)
                            exp = expeditions.get(draw_color, [])
                            draw_pile = game_data.get("draw_pile", [])
                            draws_left = len(draw_pile)
                            all_exps = game_data.get("expeditions", {})
                            total_remaining = (
                                draws_left
                                + sum(len(e) for p_exps in all_exps.values() for e in p_exps.values())
                                + sum(len(p) for p in discard_piles.values())
                                + len(hand)
                            )
                            total_remaining = 60 - total_remaining
                            scores[m["move_id"]] = _compute_play_score(
                                exp, top_card, hand, unseen, draws_left, total_remaining
                            )
                        else:
                            scores[m["move_id"]] = 0.0
                    else:
                        scores[m["move_id"]] = 0.0

        return scores

    def initial_game_data(
        self, rng_seed: int = 42, rng_state_json: str | None = None
    ) -> dict[str, Any]:
        """Return initial game state."""
        return _initial_game_data(rng_seed, rng_state_json)

    def serialize_for_screen(self, game_data: dict[str, Any]) -> dict[str, Any]:
        """Convert game_data to screen-ready format."""
        current_player = game_data.get("current_player", "player_1")
        from app.games.lost_cities.serialize import serialize_game_data
        return serialize_game_data(game_data, current_player)