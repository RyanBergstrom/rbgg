"""Tactical adviser and pre-move safety filters for Twilight Struggle RL policies.

Provides:
1. Hard tactical safety checks (e.g. DEFCON-2 battleground suicide coups, CMC coups).
2. Strategic urgency scoring (scoring card deadlines, military ops shortfall).
3. Strategic influence and coup target ranking.
4. Composite policy wrappers for MaskablePPO models or fixed policies.
"""
from __future__ import annotations

import random
from typing import Any, Callable

from app.games.twilight_struggle import rl_adapter as ra
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.scoring import SCORING_CARD_REGIONS, score_region
from app.games.twilight_struggle.turns import faction_action_limit

Selector = Callable[[Any, dict[str, Any], random.Random], int]


def _get_adapter(env: Any) -> Any:
    return env.adapter if hasattr(env, "adapter") else env


def _get_gd(env: Any) -> dict[str, Any]:
    if hasattr(env, "game_data"):
        return env.game_data
    return env.adapter.game_data


def _get_faction(env: Any) -> str:
    if hasattr(env, "faction_of") and hasattr(env, "current_player"):
        return env.faction_of(env.current_player)
    adapter = _get_adapter(env)
    return adapter.faction_of(adapter.current_player)


def _get_stage(env: Any) -> int:
    if hasattr(env, "stage"):
        return env.stage
    return _get_adapter(env).stage


def is_defcon_suicide_action(env: Any, action_id: int) -> bool:
    """Return True if taking action_id guarantees or immediately risks DEFCON 1 loss."""
    gd = _get_gd(env)
    tracks = gd.get("tracks", {})
    defcon = tracks.get("defcon", 5)
    faction = _get_faction(env)
    opponent = "ussr" if faction == "us" else "us"
    turn = gd.get("turn", 1)
    stage = _get_stage(env)
    adapter = _get_adapter(env)

    # 1. Cuban Missile Crisis check: Any coup while under CMC causes DEFCON 1 loss
    persistent = gd.get("persistent_events") or {}
    crisis = persistent.get("cuban_missile_crisis")
    if isinstance(crisis, dict) and crisis.get("faction") == faction and crisis.get("expires_turn") == turn:
        if stage == ra.STAGE_ROOT and (ra.COUP_BASE <= action_id < ra.COUP_BASE + ra.CARD_COUNT):
            return True
        if stage == ra.STAGE_COUP and (ra.COUNTRY_BASE <= action_id < ra.DONE):
            return True

    # 2. DEFCON 2 Battleground Coup check:
    # Unless US has Nuclear Subs active this turn, couping a battleground country lowers DEFCON to 1,
    # causing an immediate nuclear loss for the phasing player.
    nuclear_subs_active = (
        faction == "us"
        and isinstance(persistent.get("nuclear_subs"), dict)
        and persistent["nuclear_subs"].get("expires_turn") == turn
    )
    if defcon <= 2 and not nuclear_subs_active:
        data = load_country_data()
        if stage == ra.STAGE_COUP and (ra.COUNTRY_BASE <= action_id < ra.DONE):
            name = ra.COUNTRY_NAMES[action_id - ra.COUNTRY_BASE]
            country_info = data["countries"].get(name, {})
            if country_info.get("battleground"):
                return True
        elif stage == ra.STAGE_ROOT and (ra.COUP_BASE <= action_id < ra.COUP_BASE + ra.CARD_COUNT):
            # If playing a card for Coup at DEFCON 2, check if any non-battleground targets exist.
            # If all possible coup targets are battlegrounds, playing coup is guaranteed suicide.
            targets = adapter._coup_targets(gd, faction)
            if targets and all(data["countries"].get(t, {}).get("battleground") for t in targets):
                return True

    return False


def filter_safe_actions(env: Any, legal_actions: list[int]) -> list[int]:
    """Filter out suicide actions, falling back to full legal set if all are filtered."""
    safe = [a for a in legal_actions if not is_defcon_suicide_action(env, a)]
    return safe if safe else legal_actions


def evaluate_action_score(env: Any, action_id: int, rng: random.Random | None = None) -> float:
    """Heuristic tactical evaluation score for an action."""
    gd = _get_gd(env)
    faction = _get_faction(env)
    opponent = "ussr" if faction == "us" else "us"
    stage = _get_stage(env)
    tracks = gd.get("tracks", {})
    defcon = tracks.get("defcon", 5)
    turn = gd.get("turn", 1)
    limit = faction_action_limit(gd, faction)
    taken = gd.get("actions_taken", {}).get(faction, 0)
    rounds_remaining = max(0, limit - taken)
    data = load_country_data()

    def card_of(cid_action: int, base: int) -> dict[str, Any] | None:
        cid = cid_action - base + 1
        return next((c for c in gd.get("hands", {}).get(faction, []) if c["id"] == cid), None)

    if stage == ra.STAGE_ROOT:
        if action_id == ra.REVEAL:
            return 1000.0
        if action_id == ra.FINISH_TURN:
            return 1000.0

        if ra.HEADLINE_BASE <= action_id < ra.HEADLINE_BASE + ra.CARD_COUNT:
            card = card_of(action_id, ra.HEADLINE_BASE)
            if not card:
                return 0.0
            # Prefer playing own high-ops or advantageous events
            align_bonus = 15.0 if card.get("alignment") == faction else (-20.0 if card.get("alignment") == opponent else 0.0)
            return card.get("operations", 0) * 3.0 + align_bonus

        if action_id < ra.DISCARD_BASE:
            base = (action_id // ra.CARD_COUNT) * ra.CARD_COUNT
            card = card_of(action_id, base)
            if not card:
                return 0.0
            ops = card.get("operations", 0)
            align = card.get("alignment")

            # Scoring card urgency
            if card.get("scoring"):
                if rounds_remaining <= 2:
                    return 250.0  # Must play before turn ends!
                # If we have time, check whether the scoring favors us
                reg_name = card.get("name", "").replace("Scoring", "").replace("*", "").strip()
                if reg_name in data.get("regions", {}):
                    try:
                        sc = score_region(reg_name, gd["countries"], data)
                        delta = sc.get("vp_delta_us", 0) if faction == "us" else -sc.get("vp_delta_us", 0)
                        return 100.0 + delta * 5.0
                    except Exception:
                        pass
                return 90.0

            if base == ra.EVENT_BASE:
                if align == faction:
                    return 20.0 + ops * 2.0
                elif align == opponent:
                    return -30.0  # Dangerous to trigger opponent event
                else:
                    return 10.0 + ops * 2.0

            if base == ra.INFLUENCE_BASE:
                score = 15.0 + ops * 4.0
                if align == opponent:
                    # Playing opponent card for ops triggers event, but may be necessary
                    score -= 10.0
                return score

            if base == ra.COUP_BASE:
                if is_defcon_suicide_action(env, action_id):
                    return -500.0
                # Check military ops shortfall
                mil_ops = tracks.get("military_operations", {}).get(faction, 0)
                shortfall = max(0, defcon - mil_ops)
                urgency = (shortfall * 6.0) if rounds_remaining <= 3 else (shortfall * 2.0)
                score = 10.0 + ops * 3.0 + urgency
                if align == opponent:
                    score -= 10.0
                return score

            if base == ra.REALIGN_BASE:
                return 5.0 + ops * 2.0

        if ra.SPACE_BASE <= action_id < ra.SPACE_BASE + ra.CARD_COUNT:
            cid = action_id - ra.SPACE_BASE + 1
            card = next((c for c in gd.get("hands", {}).get(faction, []) if c["id"] == cid), None)
            if not card:
                return 0.0
            align = card.get("alignment")
            # Disposing of dangerous opponent card without triggering event
            disposal_bonus = 35.0 if align == opponent else 0.0
            return 12.0 + disposal_bonus

        if ra.CRISIS_CANCEL_BASE <= action_id < ra.CRISIS_CANCEL_BASE + len(ra.CRISIS_CANCEL_COUNTRIES):
            return 80.0

        if action_id in (ra.KAL_INFLUENCE, ra.KAL_REALIGN):
            return 80.0 if action_id == ra.KAL_INFLUENCE else 10.0

    elif stage in (ra.STAGE_INFLUENCE, ra.STAGE_KAL_INFLUENCE):
        if action_id == ra.DONE:
            return 0.0
        if ra.COUNTRY_BASE <= action_id < ra.DONE:
            name = ra.COUNTRY_NAMES[action_id - ra.COUNTRY_BASE]
            info = data["countries"].get(name, {})
            c_data = gd["countries"].get(name, {})
            mine = c_data.get(faction, 0)
            theirs = c_data.get(opponent, 0)
            stability = info.get("stability", 0) if isinstance(info.get("stability"), int) else 0
            is_bg = bool(info.get("battleground"))

            score = 0.0
            if is_bg:
                score += 25.0
            # Breakeven point to gain control
            if mine < stability <= mine + 1 and mine >= theirs:
                score += 30.0  # Secures control
            elif theirs >= stability and mine < theirs + stability:
                score += 15.0  # Contests opponent control
            elif mine < theirs:
                score += 10.0
            # Diminishing returns on over-control
            if mine > stability + 2 and mine > theirs + 2:
                score -= 15.0
            return score

    elif stage == ra.STAGE_COUP:
        if ra.COUNTRY_BASE <= action_id < ra.DONE:
            if is_defcon_suicide_action(env, action_id):
                return -500.0
            name = ra.COUNTRY_NAMES[action_id - ra.COUNTRY_BASE]
            info = data["countries"].get(name, {})
            stability = info.get("stability", 1) if isinstance(info.get("stability"), int) else 1
            theirs = gd["countries"].get(name, {}).get(opponent, 0)
            is_bg = bool(info.get("battleground"))
            # Prefer low stability battlegrounds with enemy influence
            return (40.0 if is_bg else 10.0) + (theirs * 5.0) - (stability * 8.0)

    elif stage in (ra.STAGE_REALIGN, ra.STAGE_KAL_REALIGN):
        if action_id == ra.DONE:
            return 0.0
        if ra.COUNTRY_BASE <= action_id < ra.DONE:
            name = ra.COUNTRY_NAMES[action_id - ra.COUNTRY_BASE]
            theirs = gd["countries"].get(name, {}).get(opponent, 0)
            return theirs * 5.0

    return 0.0


def adviser_policy(env: Any, observation: dict[str, Any], rng: random.Random) -> int:
    """Deterministic strategic policy with safety filters."""
    legal = [i for i, flag in enumerate(observation["action_mask"]) if flag]
    if not legal:
        return 0
    safe_legal = filter_safe_actions(env, legal)
    
    # Rerank safe legal actions by strategic evaluation score
    def key_fn(a: int) -> float:
        return evaluate_action_score(env, a, rng) + rng.random() * 0.01

    return max(safe_legal, key=key_fn)


def make_adviser_wrapped_selector(base_selector: Selector, safety_only: bool = False) -> Selector:
    """Wrap an existing selector (e.g. MaskablePPO) with safety guards and optional tactical advice."""

    def _wrapped(env: Any, observation: dict[str, Any], rng: random.Random) -> int:
        legal = [i for i, flag in enumerate(observation["action_mask"]) if flag]
        if not legal:
            return 0
        safe_legal = filter_safe_actions(env, legal)

        # Get base policy action
        base_action = base_selector(env, observation, rng)

        # If base action is safe and safety_only is requested, keep it!
        if safety_only:
            if base_action in safe_legal:
                return base_action
            # If base action was unsafe, fallback to highest scored safe alternative
            return max(safe_legal, key=lambda a: evaluate_action_score(env, a, rng))

        # Full adviser mode:
        # 1. Never take unsafe action
        if base_action not in safe_legal:
            return max(safe_legal, key=lambda a: evaluate_action_score(env, a, rng))

        # 2. In critical conditions (scoring card urgency in last 2 rounds), override base action
        stage = _get_stage(env)
        if stage == ra.STAGE_ROOT:
            gd = _get_gd(env)
            faction = _get_faction(env)
            limit = faction_action_limit(gd, faction)
            taken = gd.get("actions_taken", {}).get(faction, 0)
            if limit - taken <= 2:
                scoring_actions = [
                    a for a in safe_legal
                    if a < ra.DISCARD_BASE and any(
                        c.get("scoring") and (c["id"] == (a % ra.CARD_COUNT) + 1)
                        for c in gd.get("hands", {}).get(faction, [])
                    )
                ]
                if scoring_actions and base_action not in scoring_actions:
                    return scoring_actions[0]

        # 3. Otherwise respect base model's decision
        return base_action

    return _wrapped
