"""Validator bridge for Twilight Struggle phase and card actions."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
from typing import Any

from app.core.legal_move_interface import LegalMoveValidator
from app.core.rng import create_rng, serialize_rng
from app.games.twilight_struggle.action_rounds import execute_action_round
from app.games.twilight_struggle.actions import resolve_kal_007_bonus_action
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.crisis import cancel_cuban_missile_crisis, crisis_cancellation_targets
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.rules import controlled_by
from app.games.twilight_struggle.headlines import resolve_headline_event, reveal_headlines, submit_headline
from app.games.twilight_struggle.lifecycle import finish_turn
from app.games.twilight_struggle.interaction import (
    INTERACTION_PHASES, che_interactive_available, interaction_moves, missile_envy_interactive_available,
    _us_controls_middle_east,
    respond_interactive_event, start_interactive_event,
)
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.space_race import (
    headline_blocked_until_opponent,
    held_card_decision_pending,
    record_held_card_decision,
)
from app.games.twilight_struggle.state import create_initial_game_data
from app.games.twilight_struggle.turns import faction_action_limit, faction_can_act


def _kal_007_bonus_active(gd: dict[str, Any]) -> bool:
    bonus = (gd.get("persistent_events") or {}).get("kal_007_bonus")
    return isinstance(bonus, dict) and bonus.get("faction") == "us" and bonus.get("expires_turn") == gd.get("turn", 1)


class TwilightStruggleValidator(LegalMoveValidator):
    """Connect headline, action-round, and turn-end helpers to the engine."""

    def __init__(self) -> None:
        # Legal moves for the most recent (game_data object, player) pair. Callers treat a state as
        # immutable once built (apply_move always returns a new one), so identity plus a cheap
        # signature is a safe key; repeated membership checks within a turn reuse one result.
        self._legal_cache_key: tuple[Any, ...] | None = None
        self._legal_cache_value: list[dict[str, Any]] = []

    def _legal_moves_cached(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        gd = state.get("game_data", {})
        hands = gd.get("hands", {})
        key = (
            id(gd), player_id, gd.get("current_phase"), gd.get("current_player"), gd.get("turn"),
            gd.get("rng_state_json"), str(gd.get("headline_cards")), str(gd.get("actions_taken")),
            tuple(card.get("id") for card in hands.get("us", [])),
            tuple(card.get("id") for card in hands.get("ussr", [])),
        )
        if key != self._legal_cache_key:
            self._legal_cache_value = self.get_legal_moves(state, player_id)
            self._legal_cache_key = key
        return self._legal_cache_value

    def initial_game_data(
        self, rng_seed: int = 42, player_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        players = player_ids or ["player_1", "player_2"]
        if len(players) != 2 or len(set(players)) != 2:
            raise ValueError("Twilight Struggle requires exactly two distinct player IDs")
        data = create_initial_game_data(rng_seed)
        us_player, ussr_player = players
        data["player_by_faction"] = {"us": us_player, "ussr": ussr_player}
        data["faction_by_player"] = {us_player: "us", ussr_player: "ussr"}
        data["current_player"] = ussr_player
        data["ready_to_play"] = False
        data["blocker"] = (
            "Standard card events, complete operation options, API registration, and frontend are unfinished."
        )
        return data

    def _faction(self, game_data: dict[str, Any], player_id: str) -> str | None:
        return game_data.get("faction_by_player", {}).get(player_id)

    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        gd = state.get("game_data", {})
        faction = self._faction(gd, player_id)
        cancellations = [
            {
                "move_id": f"cancel-crisis-{faction}-{country}",
                "type": "cancel_cuban_missile_crisis", "player_id": player_id, "country": country,
            }
            for country in crisis_cancellation_targets(gd, faction)
        ]
        return cancellations + self._phase_legal_moves(state, player_id)

    def _phase_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        gd = state.get("game_data", {})
        if gd.get("game_over") or gd.get("terminal_result") is not None or gd.get("current_phase") == "game_over":
            return []
        faction = self._faction(gd, player_id)
        phase = gd.get("current_phase")
        if faction is None:
            return []
        if phase in INTERACTION_PHASES:
            return interaction_moves(gd, player_id)
        if phase == "headline":
            if gd.get("headline_cards", {}).get(faction) is not None:
                return []
            # Man in Earth Orbit (Space Race box 4): the opponent must commit and show a headline first.
            opponent = "ussr" if faction == "us" else "us"
            if headline_blocked_until_opponent(gd, faction) and gd.get("headline_cards", {}).get(opponent) is None:
                return []
            # A headline is played as an event at reveal, with no choices supplied at commit time.
            # Only cards whose event resolves without choices are offered (choice-based headlines are not yet supported).
            return [
                {"move_id": f"headline-{faction}-{card['id']}", "type": "headline", "player_id": player_id, "card_id": card["id"]}
                for card in gd.get("hands", {}).get(faction, [])
                if not card.get("scoring")
                and self._headline_event_ok(gd, card, faction)
                and self._headline_pair_playable(gd, faction, card["id"])
                and self._random_draws_resolvable(gd, card, faction)
            ]
        if phase == "turn_end":
            # Eagle/Bear has Landed (Space Race box 6): the first faction there may discard its held card.
            pending = held_card_decision_pending(gd)
            if pending:
                if faction not in pending:
                    return []
                return [
                    {
                        "move_id": f"discard-held-{faction}-{card['id']}", "type": "discard_held_card",
                        "player_id": player_id, "card_id": card["id"],
                    }
                    for card in gd.get("hands", {}).get(faction, [])
                ] + [{"move_id": f"keep-held-{faction}", "type": "keep_held_card", "player_id": player_id}]
        if gd.get("current_player") != player_id:
            return []
        if phase == "headline_reveal_ready":
            return [{"move_id": "reveal-headlines", "type": "reveal_headlines", "player_id": player_id}]
        if phase == "action_round":
            # KAL-007 bonus is an extra 4-Ops action that does not consume an action round.
            bonus_moves = []
            if faction == "us" and _kal_007_bonus_active(gd):
                bonus_moves = [{"move_id": "kal-007-bonus", "type": "kal_007_bonus", "player_id": player_id}]
            # A faction at its limit may still play held scoring cards: finish_turn refuses to close while one remains.
            at_limit = gd.get("actions_taken", {}).get(faction, 0) >= faction_action_limit(gd, faction)
            return bonus_moves + [
                {
                    "type": "play_card", "player_id": player_id,
                    "move_id": f"play-{faction}-{card['id']}",
                    "card_id": card["id"],
                    "modes": ["event"] if card.get("scoring") else ["event", "operations"],
                          **({"interactive_modes": ["event"]} if card["id"] in {20, 94, 95, 102} or
                              (card["id"] == 107 and faction == "ussr" and che_interactive_available(gd)) or
                              (card["id"] == 56 and faction == "ussr" and
                               not gd.get("persistent_events", {}).get("awacs_sale_played")) or
                              (card["id"] == 19 and faction == "us" and any(
                                  country.get("region") == "Europe" and name in gd.get("countries", {}) and
                                  controlled_by(gd["countries"][name], country) is None
                                  for name, country in load_country_data()["countries"].items()
                              )) or
                              (card["id"] == 105 and gd.get("countries", {}).get("U.K.") is not None and
                               controlled_by(gd["countries"]["U.K."], load_country_data()["countries"]["U.K."]) == "us") or
                              (card["id"] == 49 and missile_envy_interactive_available(gd, faction)) or
                              (card["id"] == 26 and (faction == "us" or card.get("alignment") == "us")) or
                              (card["id"] == 62 and (faction == "ussr" or card.get("alignment") == "ussr")) or
                              (card["id"] == 47 and faction in {"us", "ussr"}) or
                              (card["id"] == 90 and (faction == "ussr" or card.get("alignment") == "ussr") and gd.get("persistent_events", {}).get("reformer")) or
                              (card["id"] == 91 and (faction == "ussr" or card.get("alignment") == "ussr")) or
                              (card["id"] == 96 and (faction == "us" or card.get("alignment") == "us")) or
                              (card["id"] == 108 and faction == "us" and _us_controls_middle_east(gd)) or
                              (card["id"] == 10 and faction == "ussr")
                            else {"interactive_modes": ["operations"]} if (
                                (card["id"] == 10 and faction == "us") or
                                (card["id"] == 98 and faction == "us" and any(
                                    held.get("id") != 98 for held in gd.get("hands", {}).get("us", [])
                                ))
                            ) else {}),
                }
                for card in gd.get("hands", {}).get(faction, [])
                if not at_limit or card.get("scoring")
            ]
        if phase == "turn_end":
            if any(faction_can_act(gd, side) for side in ("us", "ussr")):
                return []
            if any(card.get("scoring") for side in ("us", "ussr") for card in gd.get("hands", {}).get(side, [])):
                return []
            return [{"move_id": f"finish-turn-{gd.get('turn')}", "type": "finish_turn", "player_id": player_id}]
        return []

    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        gd = state.get("game_data", {})
        if gd.get("game_over") or gd.get("terminal_result") is not None or gd.get("current_phase") == "game_over":
            return False
        player_id = move.get("player_id")
        if not isinstance(player_id, str):
            return False
        if "event_order" in move and "interactive" not in move:
            return False
        # Reject interactive=True for cards that don't support staged responses.
        if move.get("type") == "play_card" and move.get("interactive") is True:
            card_id = move.get("card_id")
            interactive_card_ids = {10, 19, 20, 26, 47, 49, 56, 62, 90, 91, 94, 95, 96, 98, 102, 105, 107, 108}
            if card_id not in interactive_card_ids:
                return False
        if move.get("type") in {"event_response", "event_bonus", "card_operations"} or "interactive" in move:
            try:
                self.apply_move(deepcopy(state), move)
            except (KeyError, TypeError, ValueError, StopIteration):
                return False
            return True
        if move.get("type") == "cancel_cuban_missile_crisis":
            # Do not use the identity cache: influence and crisis flags can change while the actor stays put.
            return move in self.get_legal_moves(state, player_id)
        if move.get("type") == "kal_007_bonus":
            # Template moves carry no operations payload, so the bonus is only valid when fully specified.
            return self._move_matches_card(state, move, player_id)
        if move in self._legal_moves_cached(state, player_id):
            return True
        if not self._move_matches_card(state, move, player_id):
            return False
        # Authoritative check: the move must apply cleanly on a copy, exactly as play would apply it.
        try:
            self.apply_move(deepcopy(state), move)
        except (KeyError, TypeError, ValueError, StopIteration):
            return False
        return True

    def _restriction_gate_ok(self, gd: dict[str, Any], card: dict[str, Any], faction: str, move: dict[str, Any]) -> bool:
        """Dry-run the action-restriction gate exactly as play would. True when the play may proceed."""
        from app.games.twilight_struggle.actions import _apply_action_restriction

        discard_id = move.get("restriction_discard_id")
        if discard_id is not None and not isinstance(discard_id, int):
            return False
        try:
            _, proceed = _apply_action_restriction(
                deepcopy(gd), faction, card["id"], move.get("mode", "event"), discard_id,
                create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}")),
            )
        except (KeyError, TypeError, ValueError):
            return False
        # A non-proceeding gate spends the round without playing the card; the bot should not choose that.
        return proceed

    def _dry_run_card_event(self, gd: dict[str, Any], card: dict[str, Any], faction: str, move: dict[str, Any], mode: str) -> bool:
        """Reject a move whose card event would fail with the supplied choices (no state is changed)."""
        rng = create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}"))
        trial = deepcopy(gd)
        # Play removes the card from the hand before its event resolves; hand-dependent random draws
        # (Five Year Plan) must see the same hand here as in apply.
        hand = trial.get("hands", {}).get(faction, [])
        held = next((i for i, c in enumerate(hand) if c.get("id") == card.get("id")), None)
        if held is not None:
            hand.pop(held)
        try:
            resolve_card_event(
                trial, card, faction, mode=mode,
                trigger_own_event=bool(move.get("trigger_own_event", False)) if mode == "operations" else False,
                country_data=load_country_data(), rng=rng,
                chosen_defcon=move.get("chosen_defcon"),
                event_choices=move.get("event_choices"),
            )
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def _random_draws_resolvable(self, gd: dict[str, Any], card: dict[str, Any], faction: str) -> bool:
        """Five Year Plan discards a random card from the USSR hand; a US-aligned draw resolves as a US event.
        Offer it only if every such draw resolves without choice input, since the reveal cannot ask for one."""
        if card.get("effect_handler") != "five_year_plan":
            return True
        for candidate in gd.get("hands", {}).get("ussr", []):
            if candidate.get("id") == card.get("id") or candidate.get("alignment") != "us" or candidate.get("scoring"):
                continue
            if not self._dry_run_card_event(gd, candidate, "us", {}, mode="event"):
                return False
        return True

    def _headline_event_ok(self, gd: dict[str, Any], card: dict[str, Any], faction: str) -> bool:
        """A headline is offered only if its event resolves with no choice or a deterministic default."""
        try:
            resolve_headline_event(
                gd, card, faction, country_data=load_country_data(),
                rng=create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}")),
            )
        except (KeyError, TypeError, ValueError, StopIteration):
            return False
        return True

    def _headline_pair_playable(self, gd: dict[str, Any], faction: str, card_id: int) -> bool:
        """Once the opponent has committed, the reveal (ops-ordered, sequential) must succeed with this card."""
        other = "ussr" if faction == "us" else "us"
        committed = dict(gd.get("headline_cards") or {})
        if committed.get(other) is None:
            return True
        committed[faction] = card_id
        trial = deepcopy(gd)
        trial["headline_cards"] = committed
        trial["current_phase"] = "headline_reveal_ready"
        hands = trial.get("hands", {})
        # Both committed headlines must still be in their owners' hands; otherwise the pair cannot reveal.
        for side in ("us", "ussr"):
            if not any(c.get("id") == committed[side] for c in hands.get(side, [])):
                return False
        try:
            reveal_headlines(trial, rng=create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}")))
        except (KeyError, TypeError, ValueError, StopIteration):
            return False
        return True

    def _validate_kal_007_bonus(self, gd: dict[str, Any], move: dict[str, Any], player_id: str) -> bool:
        if gd.get("current_phase") != "action_round" or gd.get("current_player") != player_id:
            return False
        if self._faction(gd, player_id) != "us" or not _kal_007_bonus_active(gd):
            return False
        action = move.get("operations_action")
        if not isinstance(action, dict) or action.get("type") not in {"influence", "realignment"}:
            return False
        try:
            resolve_kal_007_bonus_action(
                deepcopy(gd), action, country_data=load_country_data(),
                rng=create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}")),
            )
        except (KeyError, TypeError, ValueError):
            return False
        return True

    def _move_matches_card(self, state: dict[str, Any], move: dict[str, Any], player_id: str) -> bool:
        gd = state.get("game_data", {})
        if move.get("type") == "kal_007_bonus":
            return self._validate_kal_007_bonus(gd, move, player_id)
        if move.get("type") != "play_card" or gd.get("current_phase") != "action_round":
            return False
        if gd.get("current_player") != player_id:
            return False
        faction = self._faction(gd, player_id)
        card_id = move.get("card_id")
        card = next((c for c in gd.get("hands", {}).get(faction, []) if c.get("id") == card_id), None)
        mode = move.get("mode")
        if not card or mode not in {"event", "operations"}:
            return False
        choices = move.get("event_choices")
        if choices is not None and not isinstance(choices, dict):
            return False
        chosen_defcon = move.get("chosen_defcon")
        if chosen_defcon is not None and not (isinstance(chosen_defcon, int) and 1 <= chosen_defcon <= 5):
            return False
        # A restricted faction (Quagmire/Bear Trap) must supply a valid discard; run the real gate on a copy.
        if not self._restriction_gate_ok(gd, card, faction, move):
            return False
        if mode == "event":
            if move.get("interactive") is True and card.get("id") == 108:
                try:
                    start_interactive_event(deepcopy(state), move)
                except (KeyError, TypeError, ValueError, StopIteration):
                    return False
                return True
            if card.get("id") == 46 and chosen_defcon is None:
                # How I Learned to Stop Worrying requires an explicit DEFCON level.
                return False
            return self._dry_run_card_event(gd, card, faction, move, mode="event")
        if card.get("scoring") or not isinstance(move.get("trigger_own_event", False), bool):
            return False
        action = move.get("operations_action")
        if not isinstance(action, dict):
            return False
        kind = action.get("type")
        if kind == "space_race":
            # Shape only: eligibility (box ops, attempts left, final box) is decided by the apply-on-copy.
            # The card's event never occurs (rules 6.4.5), so no mandatory-event dry run applies.
            return True
        # Mandatory opponent/both-aligned events resolve before Ops, so their choices must also be complete.
        if not self._dry_run_card_event(gd, card, faction, move, mode="operations"):
            return False
        # Shape checks only: a mandatory event resolves before Ops, so targets are validated against the
        # post-event board by the authoritative apply-on-copy in validate_move, not against the current board.
        if kind == "influence":
            return isinstance(action.get("placements"), list)
        if kind == "coup":
            return isinstance(action.get("country"), str)
        if kind == "realignment":
            targets = action.get("targets")
            return isinstance(targets, list) and all(
                isinstance(target, dict) and isinstance(target.get("country"), str) for target in targets
            )
        return False

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(state)
        gd = result.get("game_data", {})
        # game_data owns the RNG: validation dry runs read it, so the applied move must draw from the same stream.
        if "rng_seed" in gd:
            result["rng_seed"] = gd["rng_seed"]
        if "rng_state_json" in gd:
            result["rng_state_json"] = gd["rng_state_json"]
        player_id = move["player_id"]
        faction = self._faction(gd, player_id)
        kind = move.get("type")
        if "event_order" in move and "interactive" not in move:
            raise ValueError("event_order is only accepted at an interactive Blockade Ops commitment")
        if kind in {"event_response", "event_bonus", "card_operations"}:
            return respond_interactive_event(result, move)
        if "interactive" in move:
            if kind != "play_card":
                raise ValueError("Only a card play may start an interactive event")
            return start_interactive_event(result, move)
        if gd.get("current_phase") in INTERACTION_PHASES and kind != "cancel_cuban_missile_crisis":
            raise ValueError("Resolve the pending event choice before another move")
        if kind == "cancel_cuban_missile_crisis":
            gd = cancel_cuban_missile_crisis(gd, faction, move.get("country"))
        elif kind == "headline":
            gd = submit_headline(gd, faction, move["card_id"])
            if gd["current_phase"] == "headline":
                next_faction = "us" if faction == "ussr" else "ussr"
                gd["current_player_faction"] = next_faction
                gd["current_player"] = gd.get("player_by_faction", {}).get(next_faction, next_faction)
            else:
                gd["current_player_faction"] = "ussr"
                gd["current_player"] = gd.get("player_by_faction", {}).get("ussr", "ussr")
        elif kind == "reveal_headlines":
            rng = create_rng(result.get("rng_seed", 42), result.get("rng_state_json", "{}"))
            gd = reveal_headlines(gd, rng=rng)
            gd["rng_state_json"] = serialize_rng(rng)
            result["rng_state_json"] = gd["rng_state_json"]
        elif kind == "play_card":
            result = execute_action_round(
                result, faction, move["card_id"], move["mode"],
                operations_action=move.get("operations_action"),
                trigger_own_event=move.get("trigger_own_event", False),
                chosen_defcon=move.get("chosen_defcon"),
                event_choices=move.get("event_choices"),
                restriction_discard_id=move.get("restriction_discard_id"),
            )
            played = result["game_data"]
            if played.get("current_phase") == "turn_end":
                # A faction holding Eagle/Bear has Landed decides on its held card before the turn closes.
                pending = held_card_decision_pending(played)
                if pending:
                    played["current_player"] = played.get("player_by_faction", {}).get(pending[0], pending[0])
            return result
        elif kind in {"discard_held_card", "keep_held_card"}:
            if kind == "discard_held_card":
                hand = gd["hands"][faction]
                held = next(card for card in hand if card.get("id") == move["card_id"])
                hand.remove(held)
                gd.setdefault("discard_pile", []).append(held)
            record_held_card_decision(gd, faction)
            last_actor = gd.get("current_player_faction", faction)
            gd["current_player"] = gd.get("player_by_faction", {}).get(last_actor, last_actor)
        elif kind == "kal_007_bonus":
            rng = create_rng(result.get("rng_seed", 42), result.get("rng_state_json", "{}"))
            gd = resolve_kal_007_bonus_action(
                gd, move["operations_action"], country_data=load_country_data(), rng=rng,
            )
            gd["rng_state_json"] = serialize_rng(rng)
            result["rng_state_json"] = gd["rng_state_json"]
        elif kind == "finish_turn":
            gd["rng_seed"] = result.get("rng_seed", gd.get("rng_seed", 42))
            gd["rng_state_json"] = result.get("rng_state_json", gd.get("rng_state_json", "{}"))
            gd = finish_turn(gd)
            result["rng_state_json"] = gd.get("rng_state_json", result.get("rng_state_json", "{}"))
        else:
            raise ValueError(f"Unsupported Twilight Struggle move: {kind}")
        result["game_data"] = gd
        return result

    def check_win(self, state: dict[str, Any]) -> str | None:
        gd = state.get("game_data", {})
        terminal = gd.get("terminal_result")
        if not terminal:
            return None
        return gd.get("player_by_faction", {}).get(terminal.get("winner"), terminal.get("winner"))

    def serialize_for_screen(self, game_data: dict[str, Any]) -> dict[str, Any]:
        """Hide private zones and reveal only the active faction's hand."""
        player_id = game_data.get("current_player")
        faction = game_data.get("faction_by_player", {}).get(player_id)
        screen = serialize_game_state(game_data, faction)
        if faction and player_id:
            moves = interaction_moves(game_data, player_id) if game_data.get("current_phase") in INTERACTION_PHASES else self._phase_legal_moves({"game_data": game_data}, player_id)
            if isinstance(game_data.get("_pending_event"), dict) and game_data["_pending_event"].get("our_man_tehran") and faction != "us":
                moves = []
            screen["legal_moves"] = moves
        return screen
    def ai_config(self):
        return None

    def recommend_ai_move(self, state: dict[str, Any], legal_moves: list[dict[str, Any]]) -> dict[str, Any] | None:
        return legal_moves[0] if legal_moves else None
