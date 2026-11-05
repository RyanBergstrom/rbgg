"""Fixed baseline policies for the Twilight Struggle RL adapter.

A selector is ``selector(env, observation, rng) -> action_id`` and must return an unmasked action.
``random`` and ``null`` are sanity baselines; ``rule`` is a deliberately simple v0 heuristic, not a strength claim.
"""
from __future__ import annotations

import random
from typing import Any, Callable

from app.games.twilight_struggle import rl_adapter as ra
from app.games.twilight_struggle.country_data import load_country_data

Selector = Callable[[Any, dict[str, Any], random.Random], int]


def _legal(observation: dict[str, Any]) -> list[int]:
    return [index for index, flag in enumerate(observation["action_mask"]) if flag]


def random_policy(env, observation, rng) -> int:
    return rng.choice(_legal(observation))


def null_policy(env, observation, rng) -> int:
    """Lowest-ID legal action: always the first card's event, else the first target. Deterministic."""
    del env, rng
    return _legal(observation)[0]


def rule_policy(env, observation, rng) -> int:
    """Prefer ending structural decisions quickly, own-aligned events, and battleground/high-value targets."""
    legal = _legal(observation)
    gd = env.game_data
    faction = env.faction_of(env.current_player)
    opponent = "ussr" if faction == "us" else "us"
    stage = env.stage

    def card_of(action_id: int, base: int) -> dict[str, Any] | None:
        cid = action_id - base + 1
        return next((c for c in gd.get("hands", {}).get(faction, []) if c["id"] == cid), None)

    if stage == ra.STAGE_ROOT:
        if ra.REVEAL in legal:
            return ra.REVEAL
        if ra.FINISH_TURN in legal:
            return ra.FINISH_TURN
        best, best_score = legal[0], float("-inf")
        for action_id in legal:
            score = 0.0
            if ra.HEADLINE_BASE <= action_id < ra.HEADLINE_BASE + ra.CARD_COUNT:
                card = card_of(action_id, ra.HEADLINE_BASE)
                score = (card or {}).get("operations", 0)
            elif action_id < ra.DISCARD_BASE:
                base = (action_id // ra.CARD_COUNT) * ra.CARD_COUNT
                card = card_of(action_id, base)
                if card is None:
                    continue
                if card.get("scoring"):
                    score = 100.0  # scoring cards must be played before the turn ends
                elif base == ra.EVENT_BASE:
                    score = 5.0 if card.get("alignment") == faction else -5.0
                elif base == ra.INFLUENCE_BASE:
                    score = 1.0 + card.get("operations", 0) * 0.1
                else:
                    score = -1.0  # coups/realignments risk DEFCON; v0 avoids them
            elif action_id in (ra.KAL_INFLUENCE, ra.KAL_REALIGN):
                score = 50.0 if action_id == ra.KAL_INFLUENCE else -10.0
            if score > best_score:
                best, best_score = action_id, score
        return best
    if stage in (ra.STAGE_INFLUENCE, ra.STAGE_KAL_INFLUENCE):
        countries = [a for a in legal if ra.COUNTRY_BASE <= a < ra.DONE]
        if not countries:
            return ra.DONE
        data = load_country_data()
        graph = data["adjacency"]
        superpower_name = "United States" if faction == "us" else "USSR"
        superpower_adjacent = {
            edge[0] if edge[1] == superpower_name else edge[1]
            for edge in data["superpower_adjacency"]
            if superpower_name in edge
        }
        def is_connected(name: str) -> bool:
            if name in superpower_adjacent:
                return True
            if gd["countries"].get(name, {}).get(faction, 0) > 0:
                return True
            for neighbor in graph.get(name, ()):
                if gd["countries"].get(neighbor, {}).get(faction, 0) > 0:
                    return True
            return False
        valid_countries = []
        for a in countries:
            name = ra.COUNTRY_NAMES[a - ra.COUNTRY_BASE]
            if is_connected(name):
                valid_countries.append(a)
        if not valid_countries:
            return ra.DONE
        def value(action_id: int) -> float:
            name = ra.COUNTRY_NAMES[action_id - ra.COUNTRY_BASE]
            info = data["countries"][name]
            mine = gd["countries"][name].get(faction, 0)
            theirs = gd["countries"][name].get(opponent, 0)
            stability = info["stability"] if isinstance(info["stability"], int) else 0
            return (3.0 if info["battleground"] else 0.0) + (1.5 if mine < stability <= mine + 1 else 0.0) \
                - 0.3 * mine + (0.5 if theirs > mine else 0.0) + rng.random() * 0.01
        return max(valid_countries, key=value)
    if stage == ra.STAGE_EVENT_CHOICE:
        # Event choice stage: pick the first valid choice slot (deterministic, matches default_choices order)
        choice_slots = [a for a in legal if ra.CHOICE_BASE <= a < ra.CHOICE_BASE + ra.CHOICE_SLOTS]
        if choice_slots:
            return choice_slots[0]
        return legal[0]
    if stage == ra.STAGE_RESTRICT_DISCARD:
        # Restriction discard stage: pick the first eligible discard card
        discard_actions = [a for a in legal if ra.DISCARD_BASE <= a < ra.DISCARD_BASE + ra.CARD_COUNT]
        if discard_actions:
            return discard_actions[0]
        return legal[0]
    if stage in (ra.STAGE_COUP, ra.STAGE_REALIGN, ra.STAGE_KAL_REALIGN):
        countries = [a for a in legal if ra.COUNTRY_BASE <= a < ra.DONE]
        if stage != ra.STAGE_COUP and ra.DONE in legal:
            return ra.DONE
        if countries:
            return max(
                countries,
                key=lambda a: gd["countries"][ra.COUNTRY_NAMES[a - ra.COUNTRY_BASE]].get(opponent, 0)
                + rng.random() * 0.01,
            )
    return legal[0]


FIXED_POLICIES: dict[str, Selector] = {"random": random_policy, "null": null_policy, "rule": rule_policy}
