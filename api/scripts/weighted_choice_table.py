"""Show how _weighted_choice distributes probability across moves."""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copy import deepcopy
from app.games.lost_cities.validator import LostCitiesValidator, _initial_game_data, card_color, card_value
from app.core.mcts import MCTSNode, MCTSConfig
from app.core.mcts_v3 import MCTSEngineV3

validator = LostCitiesValidator()
gd = _initial_game_data()
gd["player_hands"]["player_2"] = ["y_i", "b_7", "w_3", "y_6", "y_i", "y_8", "w_4", "y_i"]
gd["current_player"] = "player_2"
gd["current_phase"] = "play_a_card"

state = {
    "game_data": gd,
    "current_player_index": 1,
    "players": [{"player_id": "player_1", "name": "P1"}, {"player_id": "player_2", "name": "P2"}],
    "version": 1,
}

legal = validator.get_legal_moves(state, "player_2")
scores = validator.score_moves(state, "player_2", legal)

# Build move info
move_info = {}
for m in legal:
    mid = m["move_id"]
    card = m.get("card", "")
    source = m.get("source", "")
    if card:
        label = "%s:%s-%s" % (m["type"], card_color(card), card_value(card))
    else:
        label = "%s:%s" % (m["type"], source)
    move_info[mid] = {"label": label, "score": scores.get(mid, 0.0), "move": m}


def weighted_choice_no_shift(moves, weights):
    """Weighted choice WITHOUT shifting — negative weights become 0."""
    if not moves:
        return {}
    if not weights or all(w == 0.0 for w in weights):
        return __import__("random").choice(moves)

    # Clamp negatives to 0
    shifted = [max(0.0, w) for w in weights]
    total = sum(shifted)
    if total <= 0:
        return __import__("random").choice(moves)

    r = __import__("random").random() * total
    cumulative = 0.0
    for move, w in zip(moves, shifted):
        cumulative += w
        if r <= cumulative:
            return move
    return moves[-1]


# Replicate score logic without shifting
weights = [scores.get(m.get("move_id", ""), 0.0) for m in legal]
clamped = [max(0.0, w) for w in weights]
total = sum(clamped)

for m in legal:
    mid = m["move_id"]
    w = scores.get(mid, 0.0)
    c = max(0.0, w)
    move_info[mid]["clamped"] = c
    move_info[mid]["probability"] = c / total if total > 0 else 0

# Run 500 rollouts with no-shift weighted choice
first_moves = collections.Counter()
n_rollouts = 500
rng = __import__("random").Random(42)

for i in range(n_rollouts):
    sd2 = deepcopy(state)
    cp = "player_2"
    moves = validator.get_legal_moves(sd2, cp)
    move_scores = validator.score_moves(sd2, cp, moves)
    ws = [move_scores.get(m.get("move_id", ""), 0.0) for m in moves]
    chosen = weighted_choice_no_shift(moves, ws)
    first_moves[chosen["move_id"]] += 1

# Print header
print()
print("WEIGHTED CHOICE — NO SHIFTING (clamped to 0)")
print("min_w = %.2f, total_clamped = %.2f" % (min(weights), total))
print()
print("%-35s %8s %8s %7s %6s %8s" % ("Move", "Score", "Clamped", "Prob%", "Count", "Actual%"))
print("%-35s %8s %8s %7s %6s %8s" % ("-" * 35, "-" * 8, "-" * 8, "-" * 7, "-" * 6, "-" * 8))

sorted_moves = sorted(move_info.keys(), key=lambda mid: move_info[mid]["score"], reverse=True)
for mid in sorted_moves:
    info = move_info[mid]
    count = first_moves.get(mid, 0)
    actual_pct = 100.0 * count / n_rollouts
    print("%-35s %8.2f %8.2f %6.1f%% %6d %7.1f%%" % (
        info["label"], info["score"], info["clamped"],
        info["probability"] * 100, count, actual_pct
    ))

print()
print("Total rollouts: %d" % n_rollouts)
