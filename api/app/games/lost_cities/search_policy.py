"""Lost Cities evaluation policy for generic search."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from app.core.search_policy import ValidatorSearchPolicy
from app.games.lost_cities.validator import (
    COLORS,
    _can_play_to_expedition,
    _calculate_expedition_score,
    _calculate_player_score,
    card_color,
    card_number,
    compute_play_score_v2,
    is_investment,
    is_numbered,
)


class LostCitiesSearchPolicy(ValidatorSearchPolicy):
    """Lost Cities one-ply and horizon evaluation."""

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        """Apply a move and preserve search-only strategic penalties."""
        next_state = super().apply_move(state, move)
        penalty = float(state.get("_search_dead_draw_penalty", 0.0))
        if move.get("type") == "draw" and move.get("source", "").endswith("_discard"):
            color = move["source"].removesuffix("_discard")
            pile = state.get("game_data", {}).get("discard_piles", {}).get(color, [])
            if pile and self._is_dead_card(state, self.current_player(state), pile[-1]):
                # This penalty belongs to the search snapshot only; it is not
                # game state. It persists so later horizon leaves remember
                # that the branch voluntarily drew known deadwood.
                penalty += 0.12
        next_state["_search_dead_draw_penalty"] = penalty
        return next_state

    def adjust_action_values(
        self,
        state: dict[str, Any],
        moves: list[dict[str, Any]],
        values: dict[str, float],
        root_player_id: str,
    ) -> dict[str, float]:
        """Keep discards as a fallback beneath acceptable board development."""
        play_values = [
            values.get(move.get("move_id", ""), 0.0)
            for move in moves
            if move.get("type") == "play_expedition"
        ]
        best_play = max(play_values, default=0.0)
        acceptable_play = 0.25
        discard_ceiling = 0.50
        priority_margin = 0.01
        adjusted = dict(values)

        for move in moves:
            if move.get("type") != "discard":
                continue
            move_id = move.get("move_id", "")
            raw_value = adjusted.get(move_id, 0.0)
            try:
                discard_state = self.apply_move(state, move)
            except (KeyError, TypeError, ValueError):
                discard_state = state
            relief = self.discard_relief(
                state,
                move,
                discard_state,
                root_player_id,
            )
            if best_play >= acceptable_play and relief < 0.05:
                adjusted[move_id] = min(raw_value, discard_ceiling, best_play - priority_margin)
            else:
                adjusted[move_id] = min(raw_value, discard_ceiling)
        return adjusted

    def optimistic_action_bound(
        self,
        state: dict[str, Any],
        move: dict[str, Any],
        next_state: dict[str, Any],
        root_player_id: str,
    ) -> float:
        """Bound obviously poor openings without deleting hidden-card chances."""
        if move.get("type") != "play_expedition" or not is_numbered(move.get("card", "")):
            return 1.0
        game_data = state.get("game_data", {})
        color = card_color(move["card"])
        expeditions = game_data.get("expeditions", {}).get(root_player_id, {})
        if expeditions.get(color):
            return 1.0
        hand = game_data.get("player_hands", {}).get(root_player_id, [])
        card_number_played = card_number(move["card"])
        support = [
            card for card in hand
            if card != move["card"]
            and card_color(card) == color
            and is_numbered(card)
            and card_number(card) >= card_number_played
        ]
        projected = [move["card"], *support]
        projected_score = float(_calculate_expedition_score(projected))
        maximum_length = len(projected)
        if projected_score <= 0.0 and maximum_length < 4:
            return 0.12
        if projected_score <= 0.0:
            return 0.30
        return 1.0

    def is_dominated_action(
        self,
        state: dict[str, Any],
        move: dict[str, Any],
        root_player_id: str,
    ) -> bool:
        """Exclude only strategically obvious actions when alternatives exist."""
        game_data = state.get("game_data", {})
        hand = game_data.get("player_hands", {}).get(root_player_id, [])
        move_type = move.get("type")
        if move_type not in ("discard", "play_expedition"):
            return False
        card = move.get("card", "")
        if not card or "_" not in card:
            return False
        color = card_color(card)
        expedition = game_data.get("expeditions", {}).get(root_player_id, {}).get(color, [])

        if move_type == "discard" and is_investment(card):
            # A playable investment with same-color numbered support is a
            # live strategic commitment, not a reasonable early discard.
            has_numbered_support = any(
                card_color(held) == color and is_numbered(held)
                for held in hand
                if held != card
            )
            return _can_play_to_expedition(expedition, card) and has_numbered_support

        if move_type == "play_expedition" and is_numbered(card) and not expedition:
            # Do not start an expedition with a numbered card while retaining
            # playable investments of that color.
            if card_number(card) == 10:
                # Players have separate expeditions, so playing a 10 cannot
                # block the opponent's access to this color. It only creates
                # a permanent -10 endpoint for the root player.
                return True
            has_investment = any(
                card_color(held) == color and is_investment(held)
                for held in hand
                if held != card
            )
            if has_investment:
                return True

            # Once two expeditions are already active, do not commit to a
            # new numbered expedition whose known support cannot even recover
            # the -20 startup cost. This is deliberately dominance-based,
            # not a universal legality rule: if every candidate is poor, the
            # engine retains the full legal set as a fallback.
            active = sum(
                1 for cards in game_data.get("expeditions", {}).get(root_player_id, {}).values()
                if cards
            )
            if active >= 2:
                support = [
                    held for held in hand
                    if held != card
                    and card_color(held) == color
                    and is_numbered(held)
                    and card_number(held) >= card_number(card)
                ]
                projected = [card, *support]
                projected_score = float(_calculate_expedition_score(projected))
                if projected_score <= 0.0 and len(projected) < 4:
                    return True

        return False

    def score_reward(self, state: dict[str, Any], searching_player: str, winner: str | None = None) -> float:
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {})
        scores = game_data.get("scores", {})
        p1_total = scores.get("player_1", 0) + _calculate_player_score(expeditions.get("player_1", {}))
        p2_total = scores.get("player_2", 0) + _calculate_player_score(expeditions.get("player_2", {}))
        diff = p1_total - p2_total
        if searching_player == "player_2":
            diff = -diff
        return (math.tanh(diff / 100.0) + 1.0) / 2.0

    def one_ply_value(self, state: dict[str, Any], move: dict[str, Any], next_state: dict[str, Any], root_player_id: str) -> float:
        position_value = self.horizon_value(next_state, root_player_id)
        move_type = move.get("type")
        action_value = 0.5
        progress_value = self._progress_value(state, next_state, root_player_id, move)
        portfolio_before = self._portfolio_pressure(state, root_player_id)
        portfolio_after = self._portfolio_pressure(next_state, root_player_id)
        marginal_portfolio_pressure = max(0.0, portfolio_after - portfolio_before)
        if move_type == "play_expedition":
            game_data = state.get("game_data", {})
            hand = game_data.get("player_hands", {}).get(root_player_id, [])
            card = move.get("card", "")
            color = card_color(card)
            expedition = game_data.get("expeditions", {}).get(root_player_id, {}).get(color, [])
            raw_score = compute_play_score_v2(card, hand, game_data, root_player_id)
            action_value = 0.5 + 0.5 * math.tanh(raw_score / 10.0)
            if not expedition:
                action_value -= self._new_expedition_pressure(
                    state, root_player_id, color, card
                ) * 0.20
                action_value -= self._new_expedition_recovery_risk(
                    state, root_player_id, color, card
                )
            # Prefer suits with publicly available future support. This uses
            # only the root player's hand, public expeditions, and discards;
            # the opponent's hand and draw pile remain hidden.
            suit_potential = self._suit_potential(next_state, root_player_id, color)
            action_value = 0.75 * action_value + 0.25 * suit_potential
            if not expedition and is_numbered(card):
                lower_cards = [c for c in hand if card_color(c) == color and is_numbered(c) and card_number(c) < card_number(card)]
                if lower_cards:
                    action_value = min(action_value, 0.05)
                stranded_investments = [
                    c for c in hand
                    if card_color(c) == color and is_investment(c)
                ]
                if stranded_investments:
                    # Once a numbered card starts an empty expedition,
                    # investments remaining in hand can no longer be played
                    # on that expedition.
                    action_value = min(
                        action_value,
                        max(0.01, 0.10 - 0.04 * len(stranded_investments)),
                    )
        elif move_type == "discard":
            relief = self.discard_relief(state, move, next_state, root_player_id)
            action_value += 0.80 * relief
            game_data = state.get("game_data", {})
            card = move.get("card", "")
            expedition = game_data.get("expeditions", {}).get(root_player_id, {}).get(card_color(card), [])
            if self._is_dead_card(state, root_player_id, card):
                # Deadwood consumes a hand slot and cannot advance an active
                # expedition. Discarding it is useful, but it should not
                # automatically outweigh a strong live expedition plan.
                action_value = self._dead_discard_value(state, root_player_id, card)
            elif not _can_play_to_expedition(expedition, card):
                action_value = 0.65
            elif is_investment(card):
                # This is a live investment: the expedition is empty or
                # still in its investment phase. Preserve it for commitment
                # rather than treating it like ordinary discardable hand
                # material.
                action_value = 0.05
            elif is_numbered(card):
                action_value = 0.25
                if not expedition:
                    # Discarding a weak opening card avoids committing to an
                    # additional expedition. Give that avoidance the same
                    # weight as the direct weak-opening penalty.
                    action_value += self._new_expedition_recovery_risk(
                        state, root_player_id, card_color(card), card
                    )
            else:
                action_value = 0.2
        elif move_type == "draw":
            action_value = self._draw_action_value(state, next_state, move, root_player_id)

        # Immediate action quality, resulting position, and concrete progress
        # are separate signals. This prevents a neutral draw/discard cycle
        # from looking equivalent to a move that advances an expedition.
        if marginal_portfolio_pressure:
            # Apply this after branch-specific scoring so play scores cannot
            # overwrite the cost of adding work to the portfolio.
            action_value -= 0.60 * marginal_portfolio_pressure
        return self._bounded(
            max(0.0, min(1.0, 0.45 * action_value + 0.30 * position_value + 0.25 * progress_value)),
            "one_ply_value",
        )

    def discard_relief(
        self,
        state: dict[str, Any],
        move: dict[str, Any],
        next_state: dict[str, Any],
        root_player_id: str,
    ) -> float:
        """Return strategic relief from discarding instead of retaining a card."""
        if move.get("type") != "discard":
            return 0.0
        before = self._portfolio_pressure(state, root_player_id)
        after = self._portfolio_pressure(next_state, root_player_id)
        relief = max(0.0, before - after)
        card = move.get("card", "")
        if card and is_numbered(card):
            color = card_color(card)
            expedition = state.get("game_data", {}).get("expeditions", {}).get(root_player_id, {}).get(color, [])
            if not expedition:
                relief = max(
                    relief,
                    self._new_expedition_recovery_risk(state, root_player_id, color, card),
                )
        return min(1.0, relief)


    def _new_expedition_pressure(
        self,
        state: dict[str, Any],
        player_id: str,
        color: str,
        card: str,
    ) -> float:
        """Return pressure against opening a weak additional expedition."""
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        active = sum(1 for cards in expeditions.values() if cards)
        if active == 0:
            return 0.0
        support = sum(
            1 for held in hand
            if card_color(held) == color
            and held != card
            and is_numbered(held)
        )
        draw_count = len(game_data.get("draw_pile", []))
        urgency = 0.25 if draw_count > 35 else 0.60 if draw_count > 20 else 1.0
        # Existing commitments increase the cost of starting a speculative
        # suit; two or more compatible cards make the new plan viable.
        weak_plan = max(0.0, 1.0 - min(1.0, support / 2.0))
        spread = min(1.0, active / 3.0)
        return weak_plan * spread * urgency

    def _new_expedition_recovery_risk(
        self,
        state: dict[str, Any],
        player_id: str,
        color: str,
        card: str,
    ) -> float:
        """Return the graduated risk of opening an expedition unlikely to recover.

        The risk is based on the known same-color cards, the best score those
        cards could produce, and the number of existing commitments. A fifth
        expedition with substantial support can therefore be safer than a
        second expedition that cannot escape its startup cost.
        """
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        expedition = expeditions.get(color, [])
        if expedition or not is_numbered(card):
            return 0.0
        active = sum(1 for cards in expeditions.values() if cards)
        if active == 0:
            return 0.0
        hand = game_data.get("player_hands", {}).get(player_id, [])
        support_cards = [
            held for held in hand
            if held != card
            and card_color(held) == color
            and is_numbered(held)
            and card_number(held) >= card_number(card)
        ]
        projected_cards = [card, *support_cards]
        projected_score = float(_calculate_expedition_score(projected_cards))
        support_ratio = min(1.0, len(support_cards) / 4.0)
        recovery_risk = self._projected_recovery_risk(projected_score)
        support_risk = 1.0 - support_ratio
        # Every additional commitment matters, but the cost grows as the
        # player spreads further. This deliberately does not wait until the
        # fourth or fifth expedition: a hopeless third expedition should also
        # be discouraged, while an early well-supported expedition remains
        # lightly penalized.
        commitment_factor = min(1.0, (active + 1) / 4.0)
        draw_count = len(game_data.get("draw_pile", []))
        urgency = 0.25 if draw_count > 35 else 0.60 if draw_count > 20 else 1.0
        return 0.25 * commitment_factor * urgency * (
            0.45 * support_risk + 0.55 * recovery_risk
        )

    @staticmethod
    def _projected_recovery_risk(projected_score: float) -> float:
        """Map projected expedition score to a deliberately strong risk signal."""
        if projected_score <= 0.0:
            # A line that remains negative even with all known support is a
            # high-risk commitment. The deeper the hole, the closer this gets
            # to certain recovery failure.
            return 0.75 + 0.25 * min(1.0, abs(projected_score) / 20.0)
        # Positive projected lines still carry some uncertainty, but the risk
        # fades to zero as the known line develops a meaningful margin.
        return max(0.0, 0.75 - projected_score / 40.0)

    def _is_dead_card(self, state: dict[str, Any], player_id: str, card: str) -> bool:
        """Return whether a card cannot currently be played to its expedition."""
        game_data = state.get("game_data", {})
        expedition = game_data.get("expeditions", {}).get(player_id, {}).get(
            card_color(card), []
        )
        return bool(expedition) and not _can_play_to_expedition(expedition, card)

    def _dead_discard_value(
        self,
        state: dict[str, Any],
        player_id: str,
        card: str,
    ) -> float:
        """Return a calibrated preference for removing deadwood.

        Dead-card cleanup is valuable, but it is not a terminal win and must
        remain comparable with setup actions. A card is more urgent when it
        is the only dead card in hand; multiple dead cards are handled by the
        normal progress metric rather than each receiving a near-maximal
        action value.
        """
        game_data = state.get("game_data", {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        dead_count = sum(
            1 for held in hand if self._is_dead_card(state, player_id, held)
        )
        if is_investment(card):
            return 0.78 if dead_count <= 2 else 0.70
        return 0.72 if dead_count <= 2 else 0.64

    def _suit_potential(
        self,
        state: dict[str, Any],
        player_id: str,
        color: str,
    ) -> float:
        """Estimate future suit support using public information only.

        Cards in the root player's hand are known available support. Cards in
        either public expedition or discard pile are known unavailable. The
        remaining unknown cards represent possible support in the opponent's
        hidden hand or draw pile and receive partial credit.
        """
        game_data = state.get("game_data", {})
        opponent_id = "player_2" if player_id == "player_1" else "player_1"
        short = {
            "yellow": "y",
            "blue": "b",
            "white": "w",
            "green": "g",
            "red": "r",
        }[color]
        all_cards = [f"{short}_i" for _ in range(3)] + [f"{short}_{number}" for number in range(2, 11)]
        public_unavailable = Counter()
        for card in game_data.get("expeditions", {}).get(player_id, {}).get(color, []):
            public_unavailable[card] += 1
        for card in game_data.get("expeditions", {}).get(opponent_id, {}).get(color, []):
            public_unavailable[card] += 1
        for card in game_data.get("discard_piles", {}).get(color, []):
            public_unavailable[card] += 1

        own_hand = game_data.get("player_hands", {}).get(player_id, [])
        own_expedition = game_data.get("expeditions", {}).get(player_id, {}).get(color, [])
        known_support = 0.0
        unknown_support = 0.0
        for card in all_cards:
            if public_unavailable[card] > 0:
                public_unavailable[card] -= 1
                continue
            playable = _can_play_to_expedition(own_expedition, card)
            if not playable:
                continue
            if card in own_hand:
                known_support += 1.0
            else:
                # Unknown means hidden in the opponent hand or draw pile.
                unknown_support += 0.35

        support = known_support + unknown_support
        return max(0.0, min(1.0, support / 6.0))

    def _draw_action_value(
        self,
        state: dict[str, Any],
        next_state: dict[str, Any],
        move: dict[str, Any],
        root_player_id: str,
    ) -> float:
        """Score draw sources by the value of the card actually acquired."""
        source = move.get("source", "")
        if source == "draw_pile":
            # The card is hidden, so use a modest baseline plus the change in
            # hand support rather than treating every draw as identical.
            return 0.55 + 0.20 * max(
                0.0,
                self._hand_support(next_state, root_player_id)
                - self._hand_support(state, root_player_id),
            )

        color = source.replace("_discard", "")
        pile = state.get("game_data", {}).get("discard_piles", {}).get(color, [])
        if not pile:
            return 0.0
        card = pile[-1]
        expedition = state.get("game_data", {}).get("expeditions", {}).get(
            root_player_id, {}
        ).get(color, [])
        if not _can_play_to_expedition(expedition, card):
            return 0.05

        if not expedition and is_numbered(card):
            # A card can be technically playable on an empty expedition but
            # still be strategically poor. Apply the same recovery test used
            # for playing a new expedition before rewarding this discard draw.
            recovery_risk = self._new_expedition_recovery_risk(
                state, root_player_id, color, card
            )
            if recovery_risk > 0.0:
                return max(0.05, 0.55 - recovery_risk)

        hand = state.get("game_data", {}).get("player_hands", {}).get(root_player_id, [])
        if is_investment(card):
            return 0.75 if expedition and all(is_investment(c) for c in expedition) else 0.45
        raw_score = compute_play_score_v2(card, hand, state.get("game_data", {}), root_player_id)
        return self._bounded(0.55 + 0.35 * math.tanh(raw_score / 15.0), "draw_action_value")

    def _progress_value(
        self,
        state: dict[str, Any],
        next_state: dict[str, Any],
        root_player_id: str,
        move: dict[str, Any],
    ) -> float:
        """Return progress relative to the state before the candidate move."""
        before = self._progress_metric(state, root_player_id)
        after = self._progress_metric(next_state, root_player_id)
        delta = after - before
        if move.get("type") == "draw" and move.get("source", "") != "draw_pile":
            draw_value = self._draw_action_value(state, next_state, move, root_player_id)
            delta += (draw_value - 0.5) * 4.0
        if move.get("type") == "discard" and before == after:
            # A discard that neither clears deadwood nor advances an expedition
            # is a stagnation move, especially when repeated in a draw cycle.
            delta -= 1.5
        return 0.5 + 0.5 * math.tanh(delta / 5.0)

    def _progress_metric(self, state: dict[str, Any], player_id: str) -> float:
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        metric = 0.0
        for color in COLORS:
            cards = expeditions.get(color, [])
            numbered = [card_number(card) for card in cards if is_numbered(card)]
            metric += len(cards) * 2.0
            metric += max(numbered, default=0) * 0.6
            metric += sum(5.0 for card in cards if is_investment(card))
        # Useful hand support is positive, but less valuable than committed
        # expedition progress so holding cards cannot replace playing them.
        for color in COLORS:
            expedition = expeditions.get(color, [])
            highest = max(
                (card_number(card) for card in expedition if is_numbered(card)),
                default=0,
            )
            metric += sum(
                0.25
                for card in hand
                if card_color(card) == color
                and is_numbered(card)
                and card_number(card) >= highest
            )
        metric -= sum(
            4.0 if is_investment(card) else 2.5
            for card in hand
            if self._is_dead_card(state, player_id, card)
        )
        return metric

    def _hand_support(self, state: dict[str, Any], player_id: str) -> float:
        """Estimate how many held cards can currently support expeditions."""
        game_data = state.get("game_data", {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        support = 0.0
        for card in hand:
            color = card_color(card)
            if not expeditions.get(color):
                support += 0.25
            elif _can_play_to_expedition(expeditions[color], card):
                support += 0.5
        return min(1.0, support / 4.0)

    def horizon_value(self, state: dict[str, Any], root_player_id: str) -> float:
        value = self._evaluate_horizon(state, root_player_id, include_breakdown=False)
        assert isinstance(value, float)
        return value

    def explain_horizon(self, state: dict[str, Any], root_player_id: str) -> dict[str, Any]:
        """Return the horizon formula as JSON-serializable diagnostic data."""
        breakdown = self._evaluate_horizon(state, root_player_id, include_breakdown=True)
        assert isinstance(breakdown, dict)
        return breakdown

    def _evaluate_horizon(
        self,
        state: dict[str, Any],
        root_player_id: str,
        include_breakdown: bool,
    ) -> dict[str, Any] | float:
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {})
        if not expeditions:
            breakdown = {
                "relative": 0.5,
                "absolute": 0.5,
                "latent_equity": 0.5,
                "compound_setup": 0.5,
                "contributions": {
                    "relative": 0.15,
                    "absolute": 0.025,
                    "latent_equity": 0.175,
                    "compound_setup": 0.15,
                },
                "final": 0.5,
            }
            return breakdown if include_breakdown else 0.5
        scores = game_data.get("scores", {})
        hands = game_data.get("player_hands", {})
        opponent_id = "player_2" if root_player_id == "player_1" else "player_1"
        p1 = scores.get("player_1", 0) + _calculate_player_score(expeditions.get("player_1", {}))
        p2 = scores.get("player_2", 0) + _calculate_player_score(expeditions.get("player_2", {}))
        diff = p1 - p2 if root_player_id == "player_1" else p2 - p1
        relative = (math.tanh(diff / 100.0) + 1.0) / 2.0
        own_score = p1 if root_player_id == "player_1" else p2
        absolute = min(1.0, max(0.0, own_score / 50.0))

        def equity(
            player_id: str,
            player_expeditions: dict[str, list[str]],
            hand: list[str],
            collect_details: bool = False,
        ) -> float | tuple[float, list[dict[str, Any]]]:
            value = 0.0
            details: list[dict[str, Any]] = []
            for color in COLORS:
                cards = player_expeditions.get(color, [])
                if not cards:
                    continue
                numbered = [card_number(c) for c in cards if is_numbered(c)]
                highest = max(numbered, default=0)
                future = [card_number(c) for c in hand if card_color(c) == color and is_numbered(c) and card_number(c) >= highest]
                stranded = [card_number(c) for c in hand if card_color(c) == color and is_numbered(c) and card_number(c) < highest]
                # Investments remain live while the expedition contains only
                # investments. They become stranded only after a numbered
                # card has been committed to that color.
                stranded_investments = []
                if numbered:
                    stranded_investments = [
                        c for c in hand
                        if card_color(c) == color and is_investment(c)
                    ]
                investments = sum(1 for c in cards if is_investment(c))
                multiplier = 1 + investments
                current_score = float(_calculate_expedition_score(cards))
                startup_offset = 20.0
                future_value = sum(future) * 0.75 * multiplier
                stranded_value = -sum(stranded) * 0.75
                stranded_investment_value = -len(stranded_investments) * 12.0
                investment_value = investments * 10.0
                length_value = min(len(cards), 8) * 2.0
                endpoint_value = -30.0 if highest == 10 else 0.0
                eight_card_bonus_penalty = 0.0
                setup_value = 0.0
                setup_future_value = 0.0
                public_value = 0.0
                value += current_score + startup_offset
                # Every compatible future card is worth more as investments
                # compound. A second investment is therefore not merely a
                # larger immediate cost: it increases the projected value of
                # the entire playable sequence.
                value += future_value
                value += stranded_value
                value += stranded_investment_value
                value += investment_value + length_value
                if highest == 10:
                    # A 10 is an irreversible endpoint: no later numbered
                    # card can improve this expedition. Do not treat it like
                    # an ordinary developing line just because its immediate
                    # score is better than another negative setup.
                    value += endpoint_value
                if numbered:
                    # Once a numbered card starts a color, investments are
                    # no longer possible. After later numbered cards are
                    # committed, only numbers above the current highest card
                    # can be added. The eight-card bonus is impossible when
                    # that committed-plus-remaining ceiling is below eight.
                    max_possible_length = len(cards) + (10 - highest)
                    if max_possible_length < 8:
                        eight_card_bonus_penalty = (8 - max_possible_length) * 6.0
                        value -= eight_card_bonus_penalty
                    else:
                        value += 8.0
                if investments and not numbered:
                    # An investment-only expedition is an active plan, not
                    # merely a currently negative score. Reward its publicly
                    # supported continuation cards in the horizon value too.
                    setup_value = investments * 35.0
                    setup_future_value = sum(future) * 2.00 * multiplier
                    value += setup_value + setup_future_value
                if player_expeditions is expeditions.get(root_player_id, {}):
                    # Suit potential is based on public cards plus the root
                    # player's hand; it estimates support still available
                    # without inspecting the opponent's hidden hand/deck.
                    public_value = self._suit_potential(state, root_player_id, color) * 15.0
                    value += public_value
                if collect_details:
                    details.append({
                        "player": player_id,
                        "color": color,
                        "cards": list(cards),
                        "hand_future": list(future),
                        "stranded_numbers": list(stranded),
                        "stranded_investments": list(stranded_investments),
                        "investments": investments,
                        "multiplier": multiplier,
                        "current_score": current_score,
                        "startup_offset": startup_offset,
                        "future_value": future_value,
                        "stranded_value": stranded_value,
                        "stranded_investment_value": stranded_investment_value,
                        "investment_value": investment_value,
                        "length_value": length_value,
                        "endpoint_value": endpoint_value,
                        "eight_card_bonus_penalty": eight_card_bonus_penalty,
                        "setup_value": setup_value + setup_future_value,
                        "public_value": public_value,
                        "raw_equity": current_score + startup_offset + future_value + stranded_value + stranded_investment_value + investment_value + length_value + endpoint_value + setup_value + setup_future_value + public_value,
                    })
            return (value, details) if collect_details else value

        own_equity = equity(root_player_id, expeditions.get(root_player_id, {}), hands.get(root_player_id, []))
        opponent_equity = equity(opponent_id, expeditions.get(opponent_id, {}), hands.get(opponent_id, []))
        latent = own_equity - opponent_equity
        latent_equity = (math.tanh(latent / 40.0) + 1.0) / 2.0

        def compound_setup(player_id: str) -> float:
            setup = 0.0
            for color in COLORS:
                cards = expeditions.get(player_id, {}).get(color, [])
                investments = sum(1 for card in cards if is_investment(card))
                numbered = any(is_numbered(card) for card in cards)
                if investments and not numbered:
                    future = sum(
                        card_number(card)
                        for card in hands.get(player_id, [])
                        if card_color(card) == color and is_numbered(card)
                    )
                    setup += future * (1 + investments)
            return setup

        setup_diff = compound_setup(root_player_id) - compound_setup(opponent_id)
        compound_setup_value = (math.tanh(setup_diff / 40.0) + 1.0) / 2.0
        contributions = {
            "relative": 0.30 * relative,
            "absolute": 0.05 * absolute,
            "latent_equity": 0.35 * latent_equity,
            "compound_setup": 0.30 * compound_setup_value,
        }
        spread_pressure = self._spread_pressure(state, root_player_id)
        positive_horizon = sum(contributions.values())
        applied_spread_penalty = min(0.10 * spread_pressure, positive_horizon)
        contributions["spread_pressure"] = -applied_spread_penalty
        portfolio_pressure = self._portfolio_pressure(state, root_player_id)
        remaining_horizon = max(0.0, sum(contributions.values()))
        applied_portfolio_penalty = min(0.30 * portfolio_pressure, remaining_horizon)
        contributions["portfolio_pressure"] = -applied_portfolio_penalty
        dead_draw_penalty = float(state.get("_search_dead_draw_penalty", 0.0))
        remaining_horizon = max(0.0, sum(contributions.values()))
        # The penalty is explicit model output, but the policy contract still
        # requires [0, 1]. Once a branch is already at zero, additional dead
        # discard penalties cannot make it numerically below zero.
        applied_dead_draw_penalty = min(dead_draw_penalty, remaining_horizon)
        contributions["known_dead_discard_draw_penalty"] = -applied_dead_draw_penalty
        composed_final = sum(contributions.values())
        # Penalties are saturating, but keep the final policy contract robust
        # against tiny floating-point drift and unusual late-game snapshots.
        final = self._bounded(
            max(0.0, min(1.0, composed_final)),
            "horizon_value",
        )
        breakdown = {
            "relative": relative,
            "absolute": absolute,
            "latent_equity": latent_equity,
            "compound_setup": compound_setup_value,
            "spread_pressure": spread_pressure,
            "portfolio_pressure": portfolio_pressure,
            "known_dead_discard_draw_penalty": applied_dead_draw_penalty,
            "contributions": contributions,
            "final": final,
        }
        if include_breakdown:
            own_detail_equity, own_details = equity(
                root_player_id,
                expeditions.get(root_player_id, {}),
                hands.get(root_player_id, []),
                collect_details=True,
            )
            opponent_detail_equity, opponent_details = equity(
                opponent_id,
                expeditions.get(opponent_id, {}),
                hands.get(opponent_id, []),
                collect_details=True,
            )
            breakdown.update({
                "raw_equity": {
                    "root_player": own_detail_equity,
                    "opponent": opponent_detail_equity,
                    "difference": own_detail_equity - opponent_detail_equity,
                },
                "equity_by_color": own_details,
                "opponent_equity_by_color": opponent_details,
                "compound_setup_raw": {
                    "root_player": compound_setup(root_player_id),
                    "opponent": compound_setup(opponent_id),
                    "difference": setup_diff,
                },
            })
        return breakdown if include_breakdown else final

    def _spread_pressure(self, state: dict[str, Any], player_id: str) -> float:
        """Measure overcommitment to unfinished expeditions."""
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        active = 0
        weak = 0.0
        for color, cards in expeditions.items():
            if not cards:
                continue
            active += 1
            highest = max((card_number(card) for card in cards if is_numbered(card)), default=0)
            if highest:
                compatible = [
                    card for card in hand
                    if card_color(card) == color
                    and is_numbered(card)
                    and card_number(card) >= highest
                ]
                projected_score = float(_calculate_expedition_score([*cards, *compatible]))
                support_ratio = min(1.0, len(compatible) / 4.0)
                recovery_risk = self._projected_recovery_risk(projected_score)
                recovery_risk = 0.45 * (1.0 - support_ratio) + 0.55 * recovery_risk
            else:
                # An investment-only expedition remains viable when it has
                # enough numbered support to recover its startup cost.
                compatible = [
                    card for card in hand
                    if card_color(card) == color and is_numbered(card)
                ]
                projected_score = float(_calculate_expedition_score([*cards, *compatible]))
                recovery_risk = min(1.0, max(0.0, (-projected_score) / 20.0))
            if recovery_risk > 0.35:
                weak += 1.0
        draw_count = len(game_data.get("draw_pile", []))
        urgency = 0.25 if draw_count > 35 else 0.60 if draw_count > 20 else 1.0
        return min(1.0, (weak / 3.0) * urgency)

    def _portfolio_pressure(self, state: dict[str, Any], player_id: str) -> float:
        """Measure whether active expeditions exceed the player's play budget."""
        game_data = state.get("game_data", {})
        expeditions = game_data.get("expeditions", {}).get(player_id, {})
        hand = game_data.get("player_hands", {}).get(player_id, [])
        active = 0
        recovery_demand = 0

        for color, cards in expeditions.items():
            if not cards:
                continue
            active += 1
            numbered = [card_number(card) for card in cards if is_numbered(card)]
            highest = max(numbered, default=0)
            compatible = sorted(
                [
                    card for card in hand
                    if card_color(card) == color
                    and is_numbered(card)
                    and (not highest or card_number(card) >= highest)
                ],
                key=card_number,
            )
            current_score = float(_calculate_expedition_score(cards))
            if current_score > 0.0:
                continue

            projected = list(cards)
            plays_to_positive = 0
            for card in compatible:
                projected.append(card)
                plays_to_positive += 1
                if _calculate_expedition_score(projected) > 0:
                    break
            else:
                # If known cards cannot recover the expedition, count the
                # full known support as demand. This makes an unrecoverable
                # line compete directly with the player's other commitments.
                plays_to_positive = len(compatible) + 1
            recovery_demand += plays_to_positive

        draw_count = len(game_data.get("draw_pile", []))
        available_plays = max(1, draw_count // 2)
        overload = max(0.0, recovery_demand - available_plays) / max(1.0, available_plays)
        # Four colors require a meaningful portfolio justification; five is
        # treated as a substantial commitment even before overload is counted.
        commitment_hurdle = max(0.0, (active - 3) * 0.25)
        urgency = 0.25 if draw_count > 35 else 0.60 if draw_count > 20 else 1.0
        return min(1.0, (overload + commitment_hurdle) * urgency)

    @staticmethod
    def _bounded(value: float, label: str) -> float:
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{label} must be a numeric value in [0, 1]")
        return float(value)
