"""Potential-based reward shaping for Twilight Struggle RL training.

Formulation (Ng, Harada & Russell 1999):
    r'_t = r_t + gamma * Phi(s_{t+1}) - Phi(s_t)

Properties:
- Guaranteed to preserve the optimal policy of the underlying MDP.
- At terminal states, Phi(s_T) = 0.0 so end-game outcomes (+1 win / -1 loss / 0 draw)
  remain the true driving signal.
- Intermediate potential Phi(s) provides dense feedback on regional presence,
  battleground control margins, scoring card preparation, and military ops fulfillment.
"""
from __future__ import annotations

import math
from typing import Any

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.rules import control_margin, controlled_by
from app.games.twilight_struggle.scoring import classify_region, load_scoring_config
from app.games.twilight_struggle.turns import faction_action_limit


def compute_state_potential(game_data: dict[str, Any], learner_faction: str) -> float:
    """Compute bounded state potential Phi(s) in [-0.25, 0.25].
    
    Terminal states return 0.0.
    """
    if game_data.get("game_over") or game_data.get("terminal_result") is not None:
        return 0.0

    opponent = "ussr" if learner_faction == "us" else "us"
    tracks = game_data.get("tracks", {})
    board = game_data.get("countries", {})
    persistent = game_data.get("persistent_events", {})
    data = load_country_data()
    scoring_config = load_scoring_config()

    # 1. Victory Point potential V in [-1.0, 1.0]
    raw_vp = float(tracks.get("victory_points", 0))
    vp = raw_vp if learner_faction == "us" else -raw_vp
    v_norm = max(-1.0, min(1.0, vp / 20.0))

    # 2. Regional control potential R in [-1.0, 1.0]
    # Check held scoring cards for scoring card urgency
    hand = game_data.get("hands", {}).get(learner_faction, [])
    held_regions = set()
    for card in hand:
        if card.get("scoring"):
            name = card.get("name", "").replace("Scoring", "").replace("*", "").strip()
            held_regions.add(name)

    r_total = 0.0
    r_weight_sum = 0.0
    for reg_name, reg_weights in scoring_config.get("regions", {}).items():
        try:
            cl = classify_region(
                reg_name, board, data,
                formosan_resolution=bool(persistent.get("formosan_resolution")),
            )
            # Presence/Domination/Control difference
            dom_diff = 1.0 if cl["domination"][learner_faction] else (-1.0 if cl["domination"][opponent] else 0.0)
            ctrl_diff = 2.0 if cl["control"][learner_faction] else (-2.0 if cl["control"][opponent] else 0.0)
            bg_diff = (cl["battleground_count"][learner_faction] - cl["battleground_count"][opponent]) / max(1, len(cl["battlegrounds"]))

            reg_score = 0.5 * dom_diff + 0.5 * ctrl_diff + 0.3 * bg_diff
            weight = 2.0 if reg_name in held_regions else 1.0

            r_total += weight * reg_score
            r_weight_sum += weight
        except Exception:
            continue

    r_norm = max(-1.0, min(1.0, r_total / max(1.0, r_weight_sum)))

    # 3. Battleground country control potential C in [-1.0, 1.0]
    bg_favored = 0
    bg_total = 0
    for c_name, c_info in data["countries"].items():
        if c_info.get("battleground") and c_name in board:
            bg_total += 1
            ctrl = controlled_by(board[c_name], c_info)
            if ctrl == learner_faction:
                bg_favored += 1
            elif ctrl == opponent:
                bg_favored -= 1
            else:
                m_us = board[c_name].get("us", 0)
                m_ussr = board[c_name].get("ussr", 0)
                diff = (m_us - m_ussr) if learner_faction == "us" else (m_ussr - m_us)
                if diff > 0:
                    bg_favored += 0.5
                elif diff < 0:
                    bg_favored -= 0.5

    c_norm = max(-1.0, min(1.0, bg_favored / max(1, bg_total)))

    # 4. Military ops shortfall potential M in [-1.0, 1.0]
    defcon = tracks.get("defcon", 5)
    mil_ops = tracks.get("military_operations", {})
    my_ops = mil_ops.get(learner_faction, 0)
    opp_ops = mil_ops.get(opponent, 0)
    my_shortfall = max(0, defcon - my_ops)
    opp_shortfall = max(0, defcon - opp_ops)
    
    # Shortfall matters more near end of turn
    limit = faction_action_limit(game_data, learner_faction)
    taken = game_data.get("actions_taken", {}).get(learner_faction, 0)
    urgency = min(1.0, taken / max(1, limit))
    m_diff = (opp_shortfall - my_shortfall) / 5.0
    m_norm = max(-1.0, min(1.0, m_diff * urgency))

    # Combined potential bounded by tanh to [-0.25, 0.25]
    raw_sum = v_norm + 0.7 * r_norm + 0.2 * c_norm + 0.1 * m_norm
    return 0.25 * math.tanh(raw_sum)


class PotentialRewardShaper:
    """Manages potential-based reward shaping across steps of an episode."""

    def __init__(self, gamma: float = 0.9995):
        self.gamma = gamma
        self.last_potential: float = 0.0

    def reset(self, initial_game_data: dict[str, Any], learner_faction: str) -> None:
        self.last_potential = compute_state_potential(initial_game_data, learner_faction)

    def shape_reward(
        self,
        base_reward: float,
        next_game_data: dict[str, Any],
        learner_faction: str,
        is_terminal: bool,
    ) -> float:
        """Compute r'_t = r_t + gamma * Phi(s_{t+1}) - Phi(s_t)."""
        if is_terminal:
            next_potential = 0.0
        else:
            next_potential = compute_state_potential(next_game_data, learner_faction)

        shaping_delta = (self.gamma * next_potential) - self.last_potential
        self.last_potential = next_potential
        return base_reward + shaping_delta
