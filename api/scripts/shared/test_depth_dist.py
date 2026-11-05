"""Track rollout depth distribution for MCTS."""
import sys, os, random
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import LostCitiesValidator, _initial_game_data
from app.core.mcts import MCTSEngine, MCTSConfig, MCTSNode

validator = LostCitiesValidator()
config = MCTSConfig(iterations=200, exploration_constant=1.414, max_depth=500, workers=1)

seed_val = 42
random.seed(seed_val)
state = {
    "game_data": _initial_game_data(),
    "current_player_index": 0,
    "players": [
        {"player_id": "player_1", "name": "P1"},
        {"player_id": "player_2", "name": "P2"},
    ],
    "version": 0,
}

# Monkey-patch _simulate to capture depth
depths = []
orig_simulate = MCTSEngine._simulate

def patched_simulate(self, node, searching_player):
    result, finished = orig_simulate(self, node, searching_player)
    # Count depth by walking from node to root
    depth = 0
    n = node
    while n.parent is not None:
        depth += 1
        n = n.parent
    # The rollout depth is approximate: we track if it finished
    depths.append({"finished": finished, "node_depth": depth})
    return result, finished

MCTSEngine._simulate = patched_simulate

mcts = MCTSEngine(validator, config)
result = mcts.search(state, "player_1")

MCTSEngine._simulate = orig_simulate

print(f"Seed: {seed_val}")
print(f"Best move: {result.move.get('type','')}:{result.move.get('card', result.move.get('source',''))}")
print(f"Visits: {result.visit_count}, Win rate: {result.win_rate:.3f}")
print(f"Finished rounds: {result.finished_rounds}/{result.total_iterations}")
print(f"Depth limited: {result.depth_limited}/{result.total_iterations}")
print()

# Distribution of node depths (how deep in tree the leaf was)
node_depths = [d["node_depth"] for d in depths]
finished_depths = [d["node_depth"] for d in depths if d["finished"]]
depth_limited_depths = [d["node_depth"] for d in depths if not d["finished"]]

print(f"Node depth stats (how deep in tree the simulated leaf is):")
print(f"  Total rollouts: {len(depths)}")
print(f"  Finished: {len(finished_depths)}")
print(f"  Depth limited: {len(depth_limited_depths)}")
if node_depths:
    print(f"  Min node depth: {min(node_depths)}")
    print(f"  Max node depth: {max(node_depths)}")
    print(f"  Avg node depth: {sum(node_depths)/len(node_depths):.1f}")

# The real question: how many half-moves does a rollout take?
# Let's re-run with a custom simulate that counts actual rollout steps
print("\n--- Rollout step count (actual half-moves in simulation) ---")
rollout_steps = []
orig_simulate2 = MCTSEngine._simulate

def patched_simulate2(self, node, searching_player):
    import copy
    state = self._clone_state(node.state)
    game_data = state.get("game_data", {})
    current_player = self._current_player_id(state)
    original_player = searching_player
    steps = 0

    for step in range(self.config.max_depth):
        winner = self.validator.check_win(state)
        if winner is not None:
            reward = 1.0 if winner == original_player else 0.0
            rollout_steps.append({"steps": steps, "finished": True})
            return reward, True

        moves = self.validator.get_legal_moves(state, current_player)
        if not moves:
            reward = 1.0 if original_player != current_player else 0.0
            rollout_steps.append({"steps": steps, "finished": True})
            return reward, True

        move = self.rng.choice(moves)
        state = self._apply_move_to_state(state, move)
        current_player = self._current_player_id(state)
        steps += 1

    rollout_steps.append({"steps": steps, "finished": False})
    return 0.5, False

MCTSEngine._simulate = patched_simulate2

# Re-run
random.seed(seed_val)
state2 = {
    "game_data": _initial_game_data(),
    "current_player_index": 0,
    "players": [
        {"player_id": "player_1", "name": "P1"},
        {"player_id": "player_2", "name": "P2"},
    ],
    "version": 0,
}
mcts2 = MCTSEngine(validator, config)
result2 = mcts2.search(state2, "player_1")

MCTSEngine._simulate = orig_simulate2

finished_steps = [s["steps"] for s in rollout_steps if s["finished"]]
limited_steps = [s["steps"] for s in rollout_steps if not s["finished"]]

print(f"Rollout steps distribution (half-moves per rollout):")
print(f"  Total: {len(rollout_steps)}")
print(f"  Finished: {len(finished_steps)}")
print(f"  Depth limited: {len(limited_steps)}")

if finished_steps:
    # Build histogram
    counter = Counter(finished_steps)
    print(f"\n  Finished rollout depths (half-moves):")
    for depth in sorted(counter.keys()):
        count = counter[depth]
        bar = "#" * count
        print(f"    {depth:4d} steps: {count:3d} {bar}")

if limited_steps:
    print(f"\n  Depth-limited rollout steps:")
    counter_limited = Counter(limited_steps)
    for depth in sorted(counter_limited.keys()):
        count = counter_limited[depth]
        print(f"    {depth:4d} steps: {count:3d}")

print(f"\n  Overall:")
if finished_steps:
    print(f"    Finished avg steps: {sum(finished_steps)/len(finished_steps):.1f}")
    print(f"    Finished min/max: {min(finished_steps)}/{max(finished_steps)}")
if limited_steps:
    print(f"    Limited avg steps: {sum(limited_steps)/len(limited_steps):.1f}")
