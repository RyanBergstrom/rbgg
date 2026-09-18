"""MCTS rollout debug: trace heuristic weights during rollouts.

Set up a game state from a log entry, run MCTS, and log what
score_moves returns for each move so we can see how weights
influence rollout selection.

Usage:
    python -m pytest tests/test_mcts_rollout_debug.py -v -s
"""
import pytest
from copy import deepcopy

from app.games.lost_cities.validator import (
    LostCitiesValidator,
    _initial_game_data,
    _get_legal_plays,
    card_color,
    card_value,
)
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology
from app.core.mcts import MCTSConfig
from app.core.mcts_v3 import MCTSEngineV3


validator = LostCitiesValidator()

players = [
    PlayerInfo(player_id="player_1", name="P1", score=0, color="#FFFFFF"),
    PlayerInfo(player_id="player_2", name="P2", score=0, color="#333333"),
]


def _make_state(game_data, current_player="player_1"):
    game_data["current_player"] = current_player
    return GameState(
        state_id="debug",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=42,
        players=players,
        current_player_index=0 if current_player == "player_1" else 1,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id=current_player, topology=Topology.grid),
    )


def _state_dict(state):
    return {
        "players": [p.__dict__ for p in state.players],
        "current_player_index": state.current_player_index,
        "game_data": state.game_data,
        "version": state.version,
    }


def _log_scores(state_dict, player_id, label=""):
    """Print score_moves for all legal moves."""
    legal = validator.get_legal_moves(state_dict, player_id)
    scores = validator.score_moves(state_dict, player_id, legal)

    print()
    if label:
        print(f"  === {label} ===")
    print(f"  {'Move':<30s} {'Score':>8s}")
    print(f"  {'-'*30} {'-'*8}")
    for m in sorted(legal, key=lambda x: scores.get(x.get("move_id", ""), 0), reverse=True):
        mid = m.get("move_id", "")
        s = scores.get(mid, 0)
        card = m.get("card", "")
        source = m.get("source", "")
        move_type = m.get("type", "")
        if card:
            label_str = f"{move_type}:{card_color(card)}-{card_value(card)}"
        else:
            label_str = f"{move_type}:{source}"
        print(f"  {label_str:<30s} {s:>8.2f}")


def _log_rollout_weights(state_dict, player_id, n_rollouts=5, depth=40):
    """Run N rollouts from this state and log the first-move weights each time."""
    print(f"\n  === Rollout weights ({n_rollouts} rollouts, depth={depth}) ===")

    for i in range(n_rollouts):
        config = MCTSConfig(iterations=1, max_depth=depth, seed=i * 100)
        engine = MCTSEngineV3(validator, config)

        # Clone state so we don't mutate original
        sd = deepcopy(state_dict)

        # Run a single rollout manually
        from app.core.mcts import MCTSNode
        node = MCTSNode(
            state=sd,
            move={},
            parent=None,
            untried_moves=[],
            player_just_moved=player_id,
            priors={},
        )
        searching_player = player_id
        reward, finished = engine._simulate(node, searching_player)

        print(f"  Rollout {i+1}: reward={reward:.3f}, finished={finished}")


class TestMCTSRolloutDebug:
    """Debug MCTS rollouts from log entries."""

    def test_turn1_p1_empty_board(self):
        """Turn 1, player 1, empty board — from user's first log entry."""
        gd = _initial_game_data()
        gd["player_hands"]["player_1"] = [
            "r_9", "b_2", "r_i", "r_3", "b_3", "w_6", "y_i", "y_10"
        ]

        state = _make_state(gd, "player_1")
        sd = _state_dict(state)

        print("\n" + "=" * 60)
        print("TURN 1 | player_1 | play_a_card")
        print("Hand:", ", ".join(
            f"{card_color(c)}-{card_value(c)}" for c in gd["player_hands"]["player_1"]
        ))
        print("=" * 60)

        _log_scores(sd, "player_1", label="score_moves output")
        _log_rollout_weights(sd, "player_1", n_rollouts=10, depth=40)

    def test_turn1_p2_with_investments(self):
        """Turn 1, player 2, hand with green-i and green-5 — user's second log entry."""
        gd = _initial_game_data()
        gd["player_hands"]["player_2"] = [
            "w_4", "b_8", "b_5", "g_i", "y_3", "w_5", "g_5", "r_9"
        ]

        state = _make_state(gd, "player_2")
        sd = _state_dict(state)

        print("\n" + "=" * 60)
        print("TURN 1 | player_2 | play_a_card")
        print("Hand:", ", ".join(
            f"{card_color(c)}-{card_value(c)}" for c in gd["player_hands"]["player_2"]
        ))
        print("=" * 60)

        _log_scores(sd, "player_2", label="score_moves output")
        _log_rollout_weights(sd, "player_2", n_rollouts=10, depth=40)

    def test_turn1_p2_3_yellow_investments(self):
        """Turn 2, player 2, 3 yellow investments + yellow-6, yellow-8."""
        gd = _initial_game_data()
        gd["player_hands"]["player_2"] = [
            "y_i", "b_7", "w_3", "y_6", "y_i", "y_8", "w_4", "y_i"
        ]

        state = _make_state(gd, "player_2")
        sd = _state_dict(state)

        print("\n" + "=" * 60)
        print("TURN 1 | player_2 | play_a_card (3 yellow investments)")
        print("Hand:", ", ".join(
            f"{card_color(c)}-{card_value(c)}" for c in gd["player_hands"]["player_2"]
        ))
        print("=" * 60)

        _log_scores(sd, "player_2", label="score_moves output")
        _log_rollout_weights(sd, "player_2", n_rollouts=10, depth=40)

    def test_rollout_move_distribution(self):
        """Run many rollouts and count which first moves get selected."""
        gd = _initial_game_data()
        gd["player_hands"]["player_2"] = [
            "y_i", "b_7", "w_3", "y_6", "y_i", "y_8", "w_4", "y_i"
        ]

        state = _make_state(gd, "player_2")
        sd = _state_dict(state)

        print("\n" + "=" * 60)
        print("MOVE DISTRIBUTION: 3 yellow investments hand")
        print("=" * 60)

        legal = validator.get_legal_moves(sd, "player_2")
        scores = validator.score_moves(sd, "player_2", legal)

        # Show scores
        print("\n  Scores:")
        for m in sorted(legal, key=lambda x: scores.get(x.get("move_id", ""), 0), reverse=True):
            card = m.get("card", "")
            s = scores.get(m.get("move_id", ""), 0)
            print(f"    {m['type']:20s} {card_color(card):>8s}-{card_value(card):>2s}  {s:>8.2f}")

        # Run 50 rollouts and count first-move selection
        from app.core.mcts import MCTSNode
        from copy import deepcopy
        import collections

        first_moves = collections.Counter()
        n_rollouts = 50

        for i in range(n_rollouts):
            config = MCTSConfig(iterations=1, max_depth=40, seed=i * 77)
            engine = MCTSEngineV3(validator, config)
            sd2 = deepcopy(sd)

            node = MCTSNode(
                state=sd2,
                move={},
                parent=None,
                untried_moves=[],
                player_just_moved="player_2",
                priors={},
            )

            # Manually run one rollout step to see what gets picked
            state2 = engine._clone_state(node.state)
            cp = engine._current_player_id(state2)
            moves = validator.get_legal_moves(state2, cp)
            move_scores = validator.score_moves(state2, cp, moves)
            weights = [move_scores.get(m.get("move_id", ""), 0.0) for m in moves]
            chosen = engine._weighted_choice(moves, weights)

            card = chosen.get("card", "")
            if card:
                key = f"{chosen['type']}:{card_color(card)}-{card_value(card)}"
            else:
                key = f"{chosen['type']}:{chosen.get('source', '')}"
            first_moves[key] += 1

        print(f"\n  First-move selection over {n_rollouts} rollouts:")
        for move, count in first_moves.most_common():
            pct = 100.0 * count / n_rollouts
            print(f"    {move:<35s} {count:>3d} ({pct:.0f}%)")
