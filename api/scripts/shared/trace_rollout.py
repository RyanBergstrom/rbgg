"""Trace rollout to find when check_win fires."""
import sys, os, random, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import LostCitiesValidator, _initial_game_data
from app.core.mcts import MCTSEngine, MCTSConfig

validator = LostCitiesValidator()
random.seed(42)
state = {
    "game_data": _initial_game_data(),
    "current_player_index": 0,
    "players": [{"player_id": "player_1", "name": "P1"}, {"player_id": "player_2", "name": "P2"}],
    "version": 0,
}

config = MCTSConfig(iterations=1, exploration_constant=1.414, max_depth=500, workers=1)
engine = MCTSEngine(validator, config)

gs = copy.deepcopy(state)
current_player = "player_1"
for step in range(500):
    winner = validator.check_win(gs)
    if winner is not None:
        print(f"check_win returned {winner} at step {step}")
        break
    moves = validator.get_legal_moves(gs, current_player)
    if not moves:
        print(f"No moves at step {step} for {current_player}")
        break
    move = random.choice(moves)
    gs = engine._apply_move_to_state(gs, move)
    current_player = gs.get("game_data", {}).get("current_player", "")
    if step % 40 == 0:
        gd = gs.get("game_data", {})
        dp = len(gd.get("draw_pile", []))
        rnd = gd.get("round")
        ro = gd.get("round_over")
        rr = gd.get("_round_result")
        print(f"Step {step}: draw_pile={dp} round={rnd} round_over={ro} round_result={rr}")
