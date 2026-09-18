"""Simulate a full Lost Cities game where both players use MCTS v3.

Usage:
    cd api
    python -u scripts/simulate_game.py
    python -u scripts/simulate_game.py --iters 500
    python -u scripts/simulate_game.py --iters 200 --full-game
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    _calculate_player_score,
    _game_turn_number,
    card_color,
    card_value,
    COLORS,
)
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology
from app.core.mcts import MCTSConfig
from app.core.mcts_v3 import MCTSEngineV3

parser = argparse.ArgumentParser(description="Simulate full game with MCTS v3")
parser.add_argument("--iters", type=int, default=200, help="MCTS iterations per turn (default: 200)")
parser.add_argument("--depth", type=int, default=40, help="Max rollout depth (default: 40)")
parser.add_argument("--seed", type=int, default=42, help="MCTS seed (default: 42)")
parser.add_argument("--games-seed", type=int, default=99, help="Seed for game deck shuffle (default: 99)")
parser.add_argument("--full-game", action="store_true", help="Rollout entire game instead of depth-limited")
args = parser.parse_args()

validator = LostCitiesValidator()

players = [
    PlayerInfo(player_id="player_1", name="P1", score=0, color="#FFFFFF"),
    PlayerInfo(player_id="player_2", name="P2", score=0, color="#333333"),
]

state = GameState(
    state_id="sim_game",
    game_type="lost_cities",
    topology=Topology.grid,
    rng_seed=args.games_seed,
    players=players,
    current_player_index=0,
    game_data=validator.initial_game_data(),
    turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
)

state_dict = {
    "players": [p.__dict__ for p in state.players],
    "current_player_index": state.current_player_index,
    "game_data": state.game_data,
    "version": state.version,
}

config = MCTSConfig(
    iterations=args.iters,
    max_depth=args.depth,
    seed=args.seed,
    full_game_rollout=args.full_game,
)

print(f"Config: iters={args.iters}, depth={args.depth}, seed={args.seed}, full_game={args.full_game}")
print()

move_count = 0
while True:
    game_data = state_dict["game_data"]
    current_player = game_data.get("current_player")
    phase = game_data.get("current_phase")
    round_num = game_data.get("round", 1)
    turn_num = _game_turn_number(game_data)

    if game_data.get("game_over"):
        break

    # Handle round transition: if round just ended, score and reset
    if game_data.get("round_over"):
        for pid in ["player_1", "player_2"]:
            score = _calculate_player_score(game_data["expeditions"][pid])
            game_data["scores"][pid] += score

        p1r = _calculate_player_score(game_data["expeditions"]["player_1"])
        p2r = _calculate_player_score(game_data["expeditions"]["player_2"])
        print(f"\n  === Round {round_num} over ===")
        print(f"  Round scores: P1={p1r}  P2={p2r}")
        print(f"  Cumulative:   P1={game_data['scores']['player_1']}  P2={game_data['scores']['player_2']}")

        game_data["round"] += 1
        if game_data["round"] > 1:
            game_data["game_over"] = True
        else:
            validator._start_new_round(game_data)
        move_count += 1
        print()
        continue

    legal_moves = validator.get_legal_moves(state_dict, current_player)
    if not legal_moves:
        print(f"No legal moves for {current_player}, skipping turn")
        break

    # Show state
    hand = game_data["player_hands"][current_player]
    hand_str = ", ".join(f"{card_color(c)}-{card_value(c)}" for c in hand)
    expeditions = game_data.get("expeditions", {})
    discard_piles = game_data.get("discard_piles", {})
    p1_round = _calculate_player_score(expeditions.get("player_1", {}))
    p2_round = _calculate_player_score(expeditions.get("player_2", {}))
    scores = game_data.get("scores", {})
    p1_total = scores.get("player_1", 0) + p1_round
    p2_total = scores.get("player_2", 0) + p2_round

    # Board state for active player
    my_exp = expeditions.get(current_player, {})
    board_str = "  ".join(
        f"{c[:3]}:{','.join(card_value(x) for x in my_exp.get(c, [])) or '-'}"
        for c in COLORS
    )

    # Discard top cards
    discard_str = "  ".join(
        f"{c[:3]}:{card_value(discard_piles[c][-1]) if discard_piles.get(c) else '-'}"
        for c in COLORS
    )

    print(f"--- R{round_num} T{turn_num} | {current_player} | {phase} ---")
    print(f"Hand: {hand_str}")
    print(f"Board: {board_str}")
    print(f"Discard: {discard_str}")
    print(f"Score: P1={p1_total} ({scores.get('player_1', 0)}+{p1_round})  P2={p2_total} ({scores.get('player_2', 0)}+{p2_round})")

    # Run MCTS
    engine = MCTSEngineV3(validator, config)
    t0 = time.time()
    result = engine.search(state_dict, current_player)
    elapsed = time.time() - t0

    best = result.move
    move_type = best.get('type', '')
    if move_type == "discard":
        label = f"discard:{card_color(best['card'])}-{card_value(best['card'])}"
    elif move_type == "play_expedition":
        label = f"play:{card_color(best['card'])}-{card_value(best['card'])}"
    else:
        label = f"{move_type}:{best.get('source', '')}"
    print(f"  MCTS pick: {label}  (visits={result.visit_count}, win_rate={result.win_rate:.3f}, {elapsed:.1f}s)")

    # Apply move
    move_result = validator.apply_move(state_dict, best)
    state_dict["game_data"] = move_result.get("game_data", state_dict["game_data"])

    move_count += 1
    print()

# Final results
gd = state_dict["game_data"]
print("=" * 50)
print("GAME OVER")
print(f"Final scores: P1={gd['scores']['player_1']}  P2={gd['scores']['player_2']}")
if gd["scores"]["player_1"] > gd["scores"]["player_2"]:
    print("Winner: Player 1")
elif gd["scores"]["player_2"] > gd["scores"]["player_1"]:
    print("Winner: Player 2")
else:
    print("Winner: Tie (P1 wins by rule)")
print(f"Total moves: {move_count}")
