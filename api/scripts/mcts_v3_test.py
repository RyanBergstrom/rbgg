"""Run a clean MCTS v3 search test (heuristic-weighted rollout).

Usage:
    cd api
    python -u scripts/mcts_v3_test.py
    python -u scripts/mcts_v3_test.py --iters 500 --seed 42
    python -u scripts/mcts_v3_test.py --turns 4
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    _game_turn_number,
    card_color,
    card_value,
)
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology
from app.core.mcts import MCTSConfig
from app.core.mcts_v3 import MCTSEngineV3

parser = argparse.ArgumentParser(description="MCTS v3 search test")
parser.add_argument("--iters", type=int, default=200, help="Iterations (default: 200)")
parser.add_argument("--depth", type=int, default=40, help="Max rollout depth (default: 40)")
parser.add_argument("--exploration", type=float, default=1.414, help="Exploration constant (default: 1.414)")
parser.add_argument("--seed", type=int, default=42, help="MCTS seed (default: 42)")
parser.add_argument("--games-seed", type=int, default=99, help="Seed for game deck shuffle (default: 99)")
parser.add_argument("--turns", type=int, default=0, help="Simulate N turns before searching (default: 0)")
parser.add_argument("--full-game", action="store_true", help="Rollout entire game instead of depth-limited")
args = parser.parse_args()

validator = LostCitiesValidator()

players = [
    PlayerInfo(player_id="player_1", name="P1", score=0, color="#FFFFFF"),
    PlayerInfo(player_id="player_2", name="P2", score=0, color="#333333"),
]

state = GameState(
    state_id="v3_test",
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

sim_rng = random.Random(args.games_seed + 1)
current_player = "player_1"
for t in range(args.turns):
    gd = state_dict["game_data"]
    phase = gd.get("current_phase", "play_a_card")
    if phase == "draw_a_card":
        draws = validator.get_legal_moves(state_dict, current_player)
        if not draws:
            break
        move = sim_rng.choice(draws)
        result = validator.apply_move(state_dict, move)
        state_dict["game_data"] = result.get("game_data", state_dict["game_data"])
        current_player = state_dict["game_data"].get("current_player", current_player)
        if state_dict["game_data"].get("game_over"):
            break
        continue

    plays = validator.get_legal_moves(state_dict, current_player)
    if not plays:
        break
    move = sim_rng.choice(plays)
    result = validator.apply_move(state_dict, move)
    state_dict["game_data"] = result.get("game_data", state_dict["game_data"])

    draws = validator.get_legal_moves(state_dict, current_player)
    if not draws:
        break
    move = sim_rng.choice(draws)
    result = validator.apply_move(state_dict, move)
    state_dict["game_data"] = result.get("game_data", state_dict["game_data"])
    current_player = state_dict["game_data"].get("current_player", current_player)
    if state_dict["game_data"].get("game_over"):
        break

search_player = current_player
turn_num = _game_turn_number(state_dict["game_data"])

hand = state_dict["game_data"]["player_hands"][search_player]
hand_str = ", ".join(f"{card_color(c)}-{card_value(c)}" for c in hand)
print(f"Turn: {turn_num}  Player: {search_player}")
print(f"Hand: {hand_str}")

legal_moves = validator.get_legal_moves(state_dict, search_player)
print(f"Legal moves: {len(legal_moves)}")

# Show move scores
scores = validator.score_moves(state_dict, search_player, legal_moves)
print("\nMove scores:")
for m in sorted(legal_moves, key=lambda x: scores.get(x["move_id"], 0.0), reverse=True):
    ms = scores.get(m["move_id"], 0.0)
    label = f"{m['type']}:{m.get('card', m.get('source', ''))}"
    print(f"  {label:>35s}  score={ms:.2f}")

config = MCTSConfig(
    iterations=args.iters,
    exploration_constant=args.exploration,
    max_depth=args.depth,
    workers=1,
    seed=args.seed,
    full_game_rollout=args.full_game,
)

print(f"\nConfig: iters={args.iters}, depth={args.depth}, exploration={args.exploration}, seed={args.seed}, full_game={args.full_game}")
print()

engine = MCTSEngineV3(validator, config)
t0 = time.time()
result = engine.search(state_dict, search_player)
elapsed = time.time() - t0

print(f"Time: {elapsed:.2f}s")
print(f"Best move: {result.move.get('type', '')}:{result.move.get('card', result.move.get('source', ''))}")
print(f"Visit count: {result.visit_count}")
print(f"Win rate: {result.win_rate:.3f}")
print(f"Finished rounds: {result.finished_rounds}/{result.total_iterations}")
print(f"Depth limited: {result.depth_limited}/{result.total_iterations}")
print(f"Search time: {result.search_time_ms:.1f}ms")
scores = state_dict["game_data"].get("scores", {})
expeditions = state_dict["game_data"].get("expeditions", {})
from app.games.lost_cities.validator import _calculate_player_score
p1_round = _calculate_player_score(expeditions.get("player_1", {}))
p2_round = _calculate_player_score(expeditions.get("player_2", {}))
p1_total = scores.get("player_1", 0) + p1_round
p2_total = scores.get("player_2", 0) + p2_round
print(f"Scores: P1={p1_total} ({scores.get('player_1', 0)}+{p1_round})  P2={p2_total} ({scores.get('player_2', 0)}+{p2_round})")
print()
print("Top moves:")
for tm in result.top_moves[:5]:
    print(f"  {tm['move']:>30s}  visits={tm['visits']:>4d}  win_rate={tm['win_rate']:.3f}")
