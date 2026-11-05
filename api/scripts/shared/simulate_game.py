"""Simulate a full Lost Cities game where both players use hybrid MCTS.

Usage:
    cd api
    python -u scripts/simulate_game.py
    python -u scripts/simulate_game.py --iters 500
    python -u scripts/simulate_game.py --iters 200 --full-game
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    _calculate_player_score,
    card_color,
    card_value,
    COLORS,
)
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology
from app.core.mcts import MCTSConfig
from app.core.mcts import MCTSEngine


def _format_diagnostic_path(diagnostic: dict) -> str:
    """Render one compact diagnostic path for the simulation log."""
    steps = []
    for step in diagnostic.get("path", []):
        action = step.get("action") or {}
        if action.get("type") == "draw":
            steps.append(f"draw:{action.get('source', '')}")
        else:
            steps.append(
                f"{action.get('type', 'move')}:{action.get('card', action.get('move_id', ''))}"
            )
    return " -> ".join(steps)


parser = argparse.ArgumentParser(description="Simulate full game with hybrid MCTS")
parser.add_argument("--iters", type=int, default=200, help="MCTS iterations per turn (default: 200)")
parser.add_argument("--depth", type=int, default=40, help="Max rollout depth (default: 40)")
parser.add_argument("--seed", type=int, default=42, help="MCTS seed (default: 42)")
parser.add_argument("--games-seed", type=int, default=99, help="Seed for game deck shuffle (default: 99)")
parser.add_argument("--full-game", action="store_true", help="Rollout entire game instead of depth-limited")
parser.add_argument("--explain", action="store_true", help="Print bounded diagnostics for every decision")
parser.add_argument("--explain-first", action="store_true", help="Print diagnostics for the first decision only")
parser.add_argument("--diagnostic-records", type=int, default=1000, help="Maximum leaf records per search when explaining")
parser.add_argument("--max-decisions", type=int, default=0, help="Stop after this many AI decisions; 0 runs the full game")
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
    game_data=validator.initial_game_data(rng_seed=args.games_seed),
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
    strategy="hybrid",
    hot_pool_size=3,
    admission_interval=15,
    diagnostic_enabled=args.explain or args.explain_first,
    diagnostic_max_records=args.diagnostic_records,
    diagnostic_extremes_per_root=5,
)

print(
    f"Config: strategy=hybrid, iters={args.iters}, depth={args.depth}, "
    f"seed={args.seed}, full_game={args.full_game}"
)
print()

move_count = 0
display_turn_num = 1
decision_count = 0
stopped_early = False
while True:
    game_data = state_dict["game_data"]
    current_player = game_data.get("current_player")
    phase = game_data.get("current_phase")
    round_num = game_data.get("round", 1)
    turn_num = display_turn_num

    if game_data.get("game_over"):
        break
    if args.max_decisions > 0 and decision_count >= args.max_decisions:
        print(f"STOPPED after {decision_count} decisions (--max-decisions)")
        stopped_early = True
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
        display_turn_num = 1
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
    draw_pile_count = len(game_data.get("draw_pile", []))

    # Discard top cards
    discard_str = "  ".join(
        f"{c[:3]}:{card_value(discard_piles[c][-1]) if discard_piles.get(c) else '-'}"
        for c in COLORS
    )

    print(f"--- R{round_num} T{turn_num} | {current_player} | {phase} ---")
    print(f"Hand: {hand_str}")
    print(f"Board: {board_str}  draw pile: {draw_pile_count}")
    print(f"Discard: {discard_str}")
    print(f"Score: P1={p1_total} ({scores.get('player_1', 0)}+{p1_round})  P2={p2_total} ({scores.get('player_2', 0)}+{p2_round})")

    # Run MCTS
    decision_count += 1
    engine = MCTSEngine(validator, config)
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
    print(
        f"  MCTS pick: {label}  (visits={result.visit_count}, "
        f"win_rate={result.win_rate:.3f}, max_depth={result.max_depth_reached}, "
        f"avg_depth={result.average_depth:.2f}, {elapsed:.1f}s)"
    )
    print("  Considered moves:")
    for candidate in result.top_moves:
        print(
            f"    {candidate['move']} "
            f"one_ply={candidate.get('one_ply_value', 0.0):.3f} "
            f"visits={candidate['visits']} "
            f"value={candidate['win_rate']:.3f} "
            f"selection={candidate.get('selection_score', candidate['win_rate']):.3f}"
        )
    if (args.explain or args.explain_first) and result.diagnostics:
        print("  Root branch summaries:")
        for summary in result.diagnostic_summaries:
            print(
                f"    {summary['move']} | visits={summary['visits']} "
                f"average={summary['average_value']:.3f} "
                f"selection={summary['selection_score']:.3f} "
                f"one_ply={summary['one_ply_value']:.3f} "
                f"samples={summary['diagnostic_samples']}"
            )
        print("  Diagnostics: top/bottom leaf paths per root move")
        previous_root = None
        for diagnostic in result.diagnostics:
            path = diagnostic.get("path", [])
            root_move = path[0].get("move_id", "root") if path else "root"
            if root_move != previous_root:
                print(f"    ROOT {root_move}")
                previous_root = root_move
            horizon = diagnostic.get("horizon")
            line = (
                f"      value={diagnostic['value']:.3f} "
                f"depth={diagnostic['depth']} "
                f"path={_format_diagnostic_path(diagnostic)}"
            )
            if horizon:
                contributions = horizon.get("contributions", {})
                line += (
                    " | horizon: "
                    f"relative={horizon.get('relative', 0.0):.3f} "
                    f"absolute={horizon.get('absolute', 0.0):.3f} "
                    f"latent={horizon.get('latent_equity', 0.0):.3f} "
                    f"compound={horizon.get('compound_setup', 0.0):.3f} "
                    f"final={horizon.get('final', diagnostic['value']):.3f}"
                )
                line += (
                    " | contributions: "
                    + " ".join(
                        f"{name}={value:.3f}"
                        for name, value in contributions.items()
                    )
                )
                raw_equity = horizon.get("raw_equity")
                compound_raw = horizon.get("compound_setup_raw")
                if raw_equity:
                    line += (
                        " | raw_equity: "
                        f"root={raw_equity.get('root_player', 0.0):.2f} "
                        f"opponent={raw_equity.get('opponent', 0.0):.2f} "
                        f"difference={raw_equity.get('difference', 0.0):.2f}"
                    )
                if compound_raw:
                    line += (
                        " | compound_raw: "
                        f"root={compound_raw.get('root_player', 0.0):.2f} "
                        f"opponent={compound_raw.get('opponent', 0.0):.2f} "
                        f"difference={compound_raw.get('difference', 0.0):.2f}"
                    )
                equity_by_color = horizon.get("equity_by_color")
                if equity_by_color:
                    line += " | equity_by_color=" + json.dumps(
                        [
                            {
                                "color": item.get("color"),
                                "raw": round(item.get("raw_equity", 0.0), 2),
                                "cards": item.get("cards", []),
                                "future": item.get("hand_future", []),
                                "stranded": item.get("stranded_numbers", []),
                                "stranded_i": item.get("stranded_investments", []),
                                "multiplier": item.get("multiplier", 1),
                                "current": round(item.get("current_score", 0.0), 2),
                                "setup": round(item.get("setup_value", 0.0), 2),
                                "public": round(item.get("public_value", 0.0), 2),
                            }
                            for item in equity_by_color
                        ],
                        separators=(",", ":"),
                    )
            print(line)
        if args.explain_first and not args.explain:
            # Explain one decision only; subsequent turns remain normal searches.
            config.diagnostic_enabled = False

    # Apply move
    move_result = validator.apply_move(state_dict, best)
    state_dict["game_data"] = move_result.get("game_data", state_dict["game_data"])

    # Play and draw together form one displayed Lost Cities turn.
    if phase == "draw_a_card":
        display_turn_num += 1

    move_count += 1
    print()

# Final results
gd = state_dict["game_data"]
print("=" * 50)
print("SIMULATION STOPPED" if stopped_early else "GAME OVER")
print(f"Final scores: P1={gd['scores']['player_1']}  P2={gd['scores']['player_2']}")
if gd["scores"]["player_1"] > gd["scores"]["player_2"]:
    print("Winner: Player 1")
elif gd["scores"]["player_2"] > gd["scores"]["player_1"]:
    print("Winner: Player 2")
else:
    print("Winner: Tie (P1 wins by rule)")
print(f"Total moves: {move_count}")
