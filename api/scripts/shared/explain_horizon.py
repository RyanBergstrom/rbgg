"""Explain Lost Cities horizon evaluation for a hand/board fixture.

Edit the FIXTURE section below, then run from api:
    python -u scripts/explain_horizon.py

The output lists the largest positive and negative contributors first, followed
by the normalized formula components and final horizon value.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
from app.core.mcts import MCTSConfig, HybridMCTSEngine
from app.games.lost_cities.validator import (
    COLORS,
    _calculate_expedition_score,
    _calculate_player_score,
    card_color,
    card_number,
    is_investment,
    is_numbered,
    LostCitiesValidator,
)


# ── FIXTURE: edit this section for another position ─────────────────
ROOT_PLAYER = "player_2"
GAME_SEED = 99
# These are cumulative scores before the current round. Current expedition
# scores are calculated from EXPEDITIONS and added automatically.
SCORES = {"player_1": -7, "player_2": 0}
HANDS = {
    "player_1": [],
    "player_2": ["g_6", "b_6", "y_4", "r_10", "w_3", "b_2", "b_5", "b_i"],
}
EXPEDITIONS = {
    "player_1": {color: [] for color in COLORS},
    "player_2": {"blue": ["b_i"], "yellow": [], "red": [], "white": [], "green": []},
}
DISCARD_PILES = {color: [] for color in COLORS}
DRAW_PILE_COUNT = 41
# ────────────────────────────────────────────────────────────────────


def build_state() -> dict:
    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data(rng_seed=GAME_SEED)
    game_data["player_hands"] = {player: list(cards) for player, cards in HANDS.items()}
    game_data["expeditions"] = {
        player: {color: list(cards) for color, cards in expeditions.items()}
        for player, expeditions in EXPEDITIONS.items()
    }
    game_data["discard_piles"] = {
        color: list(cards) for color, cards in DISCARD_PILES.items()
    }
    game_data["scores"] = dict(SCORES)
    game_data["current_player"] = ROOT_PLAYER
    game_data["current_phase"] = "play_a_card"
    game_data["draw_pile"] = ["unknown"] * DRAW_PILE_COUNT
    game = GameState(
        state_id="horizon-explanation",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=GAME_SEED,
        players=players,
        current_player_index=0 if ROOT_PLAYER == "player_1" else 1,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id=ROOT_PLAYER, topology=Topology.grid),
    )
    return {
        "players": [player.__dict__ for player in players],
        "current_player_index": game.current_player_index,
        "game_data": game.game_data,
        "version": game.version,
    }


def expedition_equity(expeditions: dict, hand: list[str]) -> tuple[float, list[dict]]:
    rows: list[dict] = []
    total = 0.0
    for color in COLORS:
        cards = expeditions.get(color, [])
        if not cards:
            continue
        numbered = [card_number(card) for card in cards if is_numbered(card)]
        highest = max(numbered, default=0)
        future = [
            card_number(card) for card in hand
            if card_color(card) == color and is_numbered(card)
            and card_number(card) >= highest
        ]
        stranded = [
            card_number(card) for card in hand
            if card_color(card) == color and is_numbered(card)
            and card_number(card) < highest
        ]
        stranded_investments = [
            card for card in hand
            if card_color(card) == color and is_investment(card)
        ] if numbered else []
        investments = sum(1 for card in cards if is_investment(card))
        multiplier = 2 ** investments
        current = float(_calculate_expedition_score(cards))
        startup_offset = 20.0
        future_value = sum(future) * 0.75 * multiplier
        stranded_value = -sum(stranded) * 0.75
        stranded_investment_value = -len(stranded_investments) * 12.0
        investment_value = investments * 10.0
        length_value = min(len(cards), 8) * 2.0
        endpoint_value = -30.0 if highest == 10 else 0.0
        setup_investment_value = investments * 35.0 if investments and not numbered else 0.0
        setup_future_value = sum(future) * 2.0 * multiplier if investments and not numbered else 0.0
        components = {
            "current expedition score": current,
            "startup offset": startup_offset,
            "future card value": future_value,
            "stranded numbered cards": stranded_value,
            "stranded investments": stranded_investment_value,
            "committed investments": investment_value,
            "expedition length": length_value,
            "10 endpoint penalty": endpoint_value,
            "investment-only setup": setup_investment_value + setup_future_value,
        }
        color_total = sum(components.values())
        total += color_total
        rows.append({"color": color, "total": color_total, "components": components, "cards": cards, "future": future})
    return total, rows


def main() -> None:
    state = build_state()
    game_data = state["game_data"]
    opponent = "player_1" if ROOT_PLAYER == "player_2" else "player_2"
    own_expeditions = game_data["expeditions"][ROOT_PLAYER]
    opp_expeditions = game_data["expeditions"][opponent]
    own_hand = game_data["player_hands"][ROOT_PLAYER]
    opp_hand = game_data["player_hands"][opponent]
    p1 = SCORES["player_1"] + _calculate_player_score(game_data["expeditions"]["player_1"])
    p2 = SCORES["player_2"] + _calculate_player_score(game_data["expeditions"]["player_2"])
    diff = p1 - p2 if ROOT_PLAYER == "player_1" else p2 - p1
    relative = 0.5 * (1.0 + math.tanh(diff / 100.0))
    own_score = p1 if ROOT_PLAYER == "player_1" else p2
    absolute = min(1.0, max(0.0, own_score / 50.0))
    policy = HybridMCTSEngine(
        LostCitiesValidator(),
        MCTSConfig(strategy="hybrid", iterations=1, max_depth=1),
    ).policy
    own_equity, own_rows = expedition_equity(own_expeditions, own_hand)
    opp_equity, opp_rows = expedition_equity(opp_expeditions, opp_hand)
    for row in own_rows:
        suit_potential = policy._suit_potential(state, ROOT_PLAYER, row["color"])
        row["components"]["public suit potential"] = suit_potential * 15.0
        row["total"] += suit_potential * 15.0
        own_equity += suit_potential * 15.0
    latent = own_equity - opp_equity
    latent_equity = 0.5 * (1.0 + math.tanh(latent / 40.0))

    compound = 0.0
    for color in COLORS:
        cards = own_expeditions.get(color, [])
        investments = sum(1 for card in cards if is_investment(card))
        if investments and not any(is_numbered(card) for card in cards):
            future = sum(
                card_number(card) for card in own_hand
                if card_color(card) == color and is_numbered(card)
            )
            compound += future * (2 ** investments)
    opponent_compound = 0.0
    compound_setup = 0.5 * (1.0 + math.tanh((compound - opponent_compound) / 40.0))
    final_value = 0.30 * relative + 0.05 * absolute + 0.35 * latent_equity + 0.30 * compound_setup

    print("Lost Cities Horizon Explanation")
    print("=" * 80)
    print(f"root player: {ROOT_PLAYER} | scores: P1={p1}, P2={p2} | draw pile: {DRAW_PILE_COUNT}")
    print(f"hand: {', '.join(own_hand)}")
    print()
    print("Formula components (largest first)")
    print("-" * 80)
    formula_rows = sorted([
        ("relative score margin", relative, 0.30, 0.30 * relative),
        ("absolute score", absolute, 0.05, 0.05 * absolute),
        ("latent expedition equity", latent_equity, 0.35, 0.35 * latent_equity),
        ("compound setup value", compound_setup, 0.30, 0.30 * compound_setup),
    ], key=lambda row: abs(row[3]), reverse=True)
    print(f"{'component':<30} {'value':>10} {'weight':>10} {'contribution':>15}")
    for name, value, weight, contribution in formula_rows:
        print(f"{name:<30} {value:>10.4f} {weight:>10.2%} {contribution:>15.4f}")
    print(f"{'FINAL HORIZON VALUE':<30} {final_value:>10.4f}")
    print()
    print("Raw expedition equity components (largest absolute contribution first)")
    print("-" * 80)
    rows = []
    for row in own_rows:
        for name, value in row["components"].items():
            rows.append((row["color"], name, value))
    rows.sort(key=lambda row: abs(row[2]), reverse=True)
    print(f"{'color':<12} {'component':<30} {'raw value':>12}")
    for color, name, value in rows:
        print(f"{color:<12} {name:<30} {value:>12.2f}")
    print()
    print("Opponent raw equity: {:.2f}".format(opp_equity))


if __name__ == "__main__":
    main()
