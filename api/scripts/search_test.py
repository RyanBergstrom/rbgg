"""Run a single MCTS search with configurable settings.

Usage:
    cd api
    python -u scripts/search_test.py
    python -u scripts/search_test.py --iters 500 --depth 300 --seed 42
    python -u scripts/search_test.py --iters 200 --exploration 2.0
    python -u scripts/search_test.py --v2 --iters 300
    python -u scripts/search_test.py --turns 4 --v2  # skip past turn-1-2 filters
"""
import argparse
import copy
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

parser = argparse.ArgumentParser(description="Single MCTS search test")
parser.add_argument("--iters", type=int, default=200, help="Iterations (default: 200)")
parser.add_argument("--depth", type=int, default=500, help="Max rollout depth (default: 500)")
parser.add_argument("--exploration", type=float, default=1.414, help="Exploration constant (default: 1.414)")
parser.add_argument("--seed", type=int, default=42, help="MCTS seed (default: 42)")
parser.add_argument("--workers", type=int, default=1, help="Workers (default: 1)")
parser.add_argument("--v2", action="store_true", help="Use MCTS v2 (score-differential rewards)")
parser.add_argument("--games-seed", type=int, default=99, help="Seed for game deck shuffle (default: 99)")
parser.add_argument("--turns", type=int, default=0, help="Simulate N turns before searching (default: 0)")
args = parser.parse_args()

# Build game state the same way the real game does
validator = LostCitiesValidator()

players = [
    PlayerInfo(player_id="player_1", name="P1", score=0, color="#FFFFFF"),
    PlayerInfo(player_id="player_2", name="P2", score=0, color="#333333"),
]

state = GameState(
    state_id="search_test",
    game_type="lost_cities",
    topology=Topology.grid,
    rng_seed=args.games_seed,
    players=players,
    current_player_index=0,
    game_data=validator.initial_game_data(),
    turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
)

# Build state dict exactly as GameEngine._build_state_dict does
state_dict = {
    "players": [p.__dict__ for p in state.players],
    "current_player_index": state.current_player_index,
    "game_data": state.game_data,
    "version": state.version,
}

# Simulate N turns (play+draw pairs) to advance the game state
sim_rng = random.Random(args.games_seed + 1)
current_player = "player_1"
for t in range(args.turns):
    # Play/discard phase
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

    # Draw phase
    draws = validator.get_legal_moves(state_dict, current_player)
    if not draws:
        break
    move = sim_rng.choice(draws)
    result = validator.apply_move(state_dict, move)
    state_dict["game_data"] = result.get("game_data", state_dict["game_data"])
    current_player = state_dict["game_data"].get("current_player", current_player)
    if state_dict["game_data"].get("game_over"):
        break

# Determine whose turn it is for the search
search_player = current_player
turn_num = _game_turn_number(state_dict["game_data"])

config = MCTSConfig(
    iterations=args.iters,
    exploration_constant=args.exploration,
    max_depth=args.depth,
    workers=args.workers,
    seed=args.seed,
)

# Show state
hand = state_dict["game_data"]["player_hands"][search_player]
hand_str = ", ".join(f"{card_color(c)}-{card_value(c)}" for c in hand)
print(f"Turn: {turn_num}  Player: {search_player}")
print(f"Hand: {hand_str}")

legal_moves = validator.get_legal_moves(state_dict, search_player)
filtered = validator.filter_moves(state_dict, search_player, legal_moves, turn_num)
print(f"Legal moves: {len(legal_moves)} (filtered: {len(filtered)})")

# Pick engine
if args.v2:
    from app.core.mcts_v2 import MCTSEngineV2 as Engine
    engine_label = "v2 (score-differential)"
else:
    from app.core.mcts import MCTSEngine as Engine
    engine_label = "v1 (binary)"

# Patch _simulate to track rollout depth
all_rollout_depths = []
all_rollout_turns = []
orig_simulate = Engine._simulate

def patched_simulate(self, node, searching_player):
    state = self._clone_state(node.state)
    current_player = self._current_player_id(state)
    steps = 0
    for _ in range(self.config.max_depth):
        winner = self.validator.check_win(state)
        if winner is not None:
            break
        if self.validator.stop_rollout(state, current_player):
            break
        moves = self.validator.get_legal_moves(state, current_player)
        if not moves:
            break
        move = self.rng.choice(moves)
        state = self._apply_move_to_state(state, move)
        current_player = self._current_player_id(state)
        steps += 1
    all_rollout_depths.append(steps)
    all_rollout_turns.append(steps // 2)  # 2 moves per turn (play+draw)
    return orig_simulate(self, node, searching_player)

Engine._simulate = patched_simulate

# Patch _expand to track tree depth
tree_depths = []
orig_expand = Engine._expand

def patched_expand(self, node):
    child = orig_expand(self, node)
    depth = 0
    n = child
    while n.parent is not None:
        depth += 1
        n = n.parent
    tree_depths.append(depth)
    return child

Engine._expand = patched_expand

# Patch _search_sequential to capture root on the engine instance
_orig_search_seq = Engine._search_sequential

def _search_seq_capture(self, state, player_id):
    result = _orig_search_seq(self, state, player_id)
    # Walk from best child up to root
    # Actually, result has move info but not the node. Store during search loop instead.
    return result

# Better: just patch the internal method that creates root
from app.core.mcts import MCTSNode
_orig_node_init = MCTSNode.__init__
_captured_root = [None]

def _track_root(self, *args, **kwargs):
    _orig_node_init(self, *args, **kwargs)
    if _captured_root[0] is None and self.parent is None:
        _captured_root[0] = self

MCTSNode.__init__ = _track_root

print(f"Engine: {engine_label}")
print(f"Config: iters={args.iters}, depth={args.depth}, exploration={args.exploration}, workers={args.workers}, seed={args.seed}")
print()

mcts = Engine(validator, config)
t0 = time.time()
result = mcts.search(state_dict, search_player)
elapsed = time.time() - t0

# Grab root before restoring patches
root = _captured_root[0]
_captured_root[0] = None  # reset for next run
MCTSNode.__init__ = _orig_node_init

Engine._simulate = orig_simulate
Engine._expand = orig_expand

import statistics
from collections import deque

def _iter_tree(node):
    """Yield all nodes in the tree via BFS."""
    queue = deque([node])
    while queue:
        n = queue.popleft()
        yield n
        for child in n.children:
            queue.append(child)

avg_depth = statistics.mean(all_rollout_depths) if all_rollout_depths else 0
med_depth = statistics.median(all_rollout_depths) if all_rollout_depths else 0
max_depth_reached = max(all_rollout_depths) if all_rollout_depths else 0
min_depth_reached = min(all_rollout_depths) if all_rollout_depths else 0
avg_turns = statistics.mean(all_rollout_turns) if all_rollout_turns else 0
med_turns = statistics.median(all_rollout_turns) if all_rollout_turns else 0
max_turns = max(all_rollout_turns) if all_rollout_turns else 0
min_turns = min(all_rollout_turns) if all_rollout_turns else 0

# BFS tree width analysis
def get_tree_widths(root):
    if not root:
        return []
    widths = []
    queue = deque([(root, 0)])
    current_depth = 0
    current_count = 0
    while queue:
        node, depth = queue.popleft()
        if depth > current_depth:
            widths.append(current_count)
            current_depth = depth
            current_count = 0
        current_count += 1
        for child in node.children:
            queue.append((child, depth + 1))
    widths.append(current_count)
    return widths

widths = get_tree_widths(root)
max_width = max(widths) if widths else 0
max_width_level = widths.index(max_width) if widths else 0

# Average branching factor: total children / expanded parents
total_children = sum(len(n.children) for n in _iter_tree(root))
total_parents = sum(1 for n in _iter_tree(root) if n.children)
avg_bf = total_children / total_parents if total_parents else 0

print(f"Time: {elapsed:.2f}s")
print(f"Best move: {result.move.get('type', '')}:{result.move.get('card', result.move.get('source', ''))}")
print(f"Visit count: {result.visit_count}")
print(f"Win rate: {result.win_rate:.3f}")
print(f"Finished rounds: {result.finished_rounds}/{result.total_iterations}")
print(f"Depth limited: {result.depth_limited}/{result.total_iterations}")
print(f"Rollout depth: min={min_depth_reached}, max={max_depth_reached}, avg={avg_depth:.1f}, median={med_depth:.1f}")
print(f"Rollout turns: min={min_turns}, max={max_turns}, avg={avg_turns:.1f}, median={med_turns:.1f}")
print(f"Tree nodes: {total_parents + 1}  depth={len(widths) - 1}  max_width={max_width} (level {max_width_level})  avg_branching={avg_bf:.1f}")
print(f"Level widths: {widths}")
print()
print("Top moves:")
for tm in result.top_moves[:5]:
    print(f"  {tm['move']:>30s}  visits={tm['visits']:>4d}  win_rate={tm['win_rate']:.3f}")
