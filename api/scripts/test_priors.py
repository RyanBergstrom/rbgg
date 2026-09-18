"""Quick test of priors/filters integration."""
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import LostCitiesValidator, _initial_game_data, card_color, card_value
from app.core.mcts import MCTSEngine, MCTSConfig

validator = LostCitiesValidator()
config = MCTSConfig(iterations=100, exploration_constant=1.414, max_depth=200, workers=1)

for seed_val in [42, 123, 456, 789]:
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

    # Show hand
    hand = state["game_data"]["player_hands"]["player_1"]
    hand_str = ", ".join(f"{card_color(c)}-{card_value(c)}" for c in hand)
    print(f"\nSeed {seed_val} | Hand: {hand_str}")

    # Show filtered moves
    legal_moves = validator.get_legal_moves(state, "player_1")
    filtered = validator.filter_moves(state, "player_1", legal_moves, 0)
    priors = validator.prior_moves(state, "player_1", filtered, 0)

    print(f"  Legal moves: {len(legal_moves)} -> Filtered: {len(filtered)}")
    print(f"  Priors: {len([p for p in priors.values() if p != 0.0])} non-zero out of {len(priors)}")
    for m in filtered:
        mid = m.get("move_id", "")
        p = priors.get(mid, 0.0)
        label = m.get("type", "") + ":" + m.get("card", m.get("source", ""))
        if p != 0.0:
            print(f"    {label} -> prior={p:+.1f}")

    # Run MCTS
    mcts = MCTSEngine(validator, config)
    result = mcts.search(state, "player_1")
    print(f"  MCTS best: {result.move.get('type','')}:{result.move.get('card', result.move.get('source',''))} visits={result.visit_count} wr={result.win_rate:.3f} finished={result.finished_rounds}/{result.total_iterations} depth_lim={result.depth_limited}")
    for tm in result.top_moves[:5]:
        print(f"    {tm['move']}: visits={tm['visits']} wr={tm['win_rate']}")
