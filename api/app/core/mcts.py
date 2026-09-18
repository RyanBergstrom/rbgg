"""Generic Monte Carlo Tree Search (MCTS) engine.

Game-agnostic — operates exclusively through the ``LegalMoveValidator``
interface. Any game that implements ``get_legal_moves``, ``apply_move``,
and ``check_win`` gets MCTS support automatically.

Supports root parallelism: when ``MCTSConfig.workers > 1``, independent
MCTS searches run in parallel across CPU cores via ``ProcessPoolExecutor``,
and visit counts are merged to select the best move.

Usage::

    from app.core.mcts import MCTSEngine, MCTSConfig
    engine = MCTSEngine(validator, MCTSConfig(iterations=500))
    result = engine.search(state_dict, player_id)
    chosen_move = result.move
"""
from __future__ import annotations

import concurrent.futures
import copy
import math
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.legal_move_interface import LegalMoveValidator
from app.core.log import suppress_tracing, trace


# ── Configuration ───────────────────────────────────────────────────

@dataclass
class MCTSConfig:
    """Tuning parameters for the MCTS search."""

    iterations: int = 1000
    exploration_constant: float = 1.414  # sqrt(2)
    max_depth: int = 100
    seed: int | None = None
    workers: int = 1  # number of parallel workers (root parallelism)
    full_game_rollout: bool = False  # if True, rollout runs until game ends (ignores max_depth)


@dataclass
class MCTSResult:
    """Output of an MCTS search."""

    move: dict[str, Any]
    visit_count: int
    win_rate: float
    total_iterations: int
    search_time_ms: float
    top_moves: list[dict[str, Any]] = field(default_factory=list)
    finished_rounds: int = 0
    depth_limited: int = 0


# ── Tree Node ───────────────────────────────────────────────────────

@dataclass
class MCTSNode:
    """A node in the MCTS search tree."""

    state: dict[str, Any]
    move: dict[str, Any] | None  # move that led to this state (None for root)
    parent: MCTSNode | None
    children: list[MCTSNode] = field(default_factory=list)
    visits: int = 0
    wins: float = 0.0
    untried_moves: list[dict[str, Any]] = field(default_factory=list)
    player_just_moved: str | None = None
    priors: dict[str, float] = field(default_factory=dict)  # move_id → prior value

    def is_fully_expanded(self) -> bool:
        return len(self.untried_moves) == 0

    def is_terminal(self) -> bool:
        return len(self.children) == 0 and len(self.untried_moves) == 0

    def uct_value(self, exploration_constant: float) -> float:
        """Upper Confidence Bound applied to Trees (UCT) value.

        Returns ``inf`` for unvisited nodes so they are always explored.
        Includes a prior bonus that decays with visit count.
        """
        if self.visits == 0:
            return float("inf")
        if self.parent is None:
            return float("inf")
        exploitation = self.wins / self.visits
        exploration = exploration_constant * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )
        move_id = self.move.get("move_id", "") if self.move else ""
        prior_bonus = self.priors.get(move_id, 0.0) / (1 + self.visits)
        return exploitation + exploration + prior_bonus

    def best_child(self, exploration_constant: float) -> MCTSNode:
        """Return the child with the highest UCT value."""
        return max(self.children, key=lambda c: c.uct_value(exploration_constant))


# ── MCTS Engine ─────────────────────────────────────────────────────

class MCTSEngine:
    """Generic Monte Carlo Tree Search engine.

    Works with any ``LegalMoveValidator`` — no game-specific MCTS code needed.

    When ``config.workers > 1``, uses root parallelism: independent MCTS
    searches run in parallel via ``ProcessPoolExecutor``, and visit counts
    are merged to select the best move.
    """

    def __init__(
        self,
        validator: LegalMoveValidator,
        config: MCTSConfig | None = None,
    ) -> None:
        self.validator = validator
        self.config = config or MCTSConfig()
        self.rng = random.Random(self.config.seed)

    # ── Public API ───────────────────────────────────────────────────

    def search(self, state: dict[str, Any], player_id: str) -> MCTSResult:
        """Run MCTS from *state* and return the best move for *player_id*.

        Args:
            state: Full state dict (as built by ``GameEngine._build_state_dict``).
            player_id: The player whose turn it is.

        Returns:
            ``MCTSResult`` with the chosen move and statistics.
        """
        t0 = time.perf_counter()

        with suppress_tracing():
            if self.config.workers > 1:
                result = self._search_parallel(state, player_id)
            else:
                result = self._search_sequential(state, player_id)

        result.search_time_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Log summary (outside suppress_tracing so it actually logs)
        trace("mcts", "search_result",
              player_id=player_id,
              iterations=result.total_iterations,
              best_move=result.move.get("type", "") + ":" + result.move.get("card", result.move.get("source", "")),
              visit_count=result.visit_count,
              win_rate=round(result.win_rate, 3),
              search_ms=result.search_time_ms,
              finished_rounds=result.finished_rounds,
              depth_limited=result.depth_limited,
              top_moves=result.top_moves,
              )

        return result

    # ── Sequential search (single-threaded) ──────────────────────────

    def _search_sequential(
        self, state: dict[str, Any], player_id: str
    ) -> MCTSResult:
        """Standard single-threaded MCTS search."""
        root_state = self._clone_state(state)
        root_state["current_player_index"] = self._find_player_index(root_state, player_id)

        game_data = root_state.get("game_data", {})
        turn_number = game_data.get("round", 0)

        legal_moves = self.validator.get_legal_moves(root_state, player_id)
        # Apply game-specific move filters (turn-1-2 only)
        legal_moves = self.validator.filter_moves(root_state, player_id, legal_moves, turn_number)
        # Compute priors for root-level moves
        root_priors = self.validator.prior_moves(root_state, player_id, legal_moves, turn_number)

        root = MCTSNode(
            state=root_state,
            move=None,
            parent=None,
            untried_moves=list(legal_moves),
            player_just_moved=self._get_opponent(player_id),
            priors=root_priors,
        )

        finished_rounds = 0
        depth_limited = 0
        for _ in range(self.config.iterations):
            node = self._select(root)
            if not node.is_terminal() and not node.is_fully_expanded():
                node = self._expand(node)
            reward, finished = self._simulate(node, player_id)
            if finished:
                finished_rounds += 1
            else:
                depth_limited += 1
            self._backpropagate(node, reward, player_id)

        best = max(root.children, key=lambda c: c.visits)

        # Collect top move stats for logging
        sorted_children = sorted(root.children, key=lambda c: c.visits, reverse=True)
        top_moves = []
        for c in sorted_children[:5]:
            move = c.move or {}
            win_rate = c.wins / c.visits if c.visits > 0 else 0.0
            top_moves.append({
                "move": move.get("type", "") + ":" + move.get("card", move.get("source", "")),
                "visits": c.visits,
                "win_rate": round(win_rate, 3),
            })

        return MCTSResult(
            move=best.move,
            visit_count=best.visits,
            win_rate=best.wins / best.visits if best.visits > 0 else 0.0,
            total_iterations=self.config.iterations,
            search_time_ms=0.0,
            top_moves=top_moves,
            finished_rounds=finished_rounds,
            depth_limited=depth_limited,
        )

    # ── Parallel search (root parallelism) ───────────────────────────

    def _search_parallel(
        self, state: dict[str, Any], player_id: str
    ) -> MCTSResult:
        """Run independent MCTS searches in parallel and merge visit counts.

        Each worker runs its own MCTS tree from the same root state with a
        different RNG seed. After all workers finish, visit counts per move
        are merged and the move with the highest total visits is selected.
        """
        workers = min(self.config.workers, os.cpu_count() or 1)
        iters_per_worker = self.config.iterations // workers
        remainder = self.config.iterations - iters_per_worker * workers

        # Build tasks: each worker gets a unique seed and iteration count
        base_seed = self.config.seed if self.config.seed is not None else random.randint(0, 2**32)
        engine_class_name = type(self).__name__
        tasks = []
        for i in range(workers):
            worker_iters = iters_per_worker + (1 if i < remainder else 0)
            worker_seed = base_seed + i
            tasks.append((
                state,
                player_id,
                {
                    "iterations": worker_iters,
                    "exploration_constant": self.config.exploration_constant,
                    "max_depth": self.config.max_depth,
                    "seed": worker_seed,
                    "workers": 1,  # each worker runs sequentially
                },
                worker_iters,
                engine_class_name,
            ))

        # Run workers in parallel
        merged_visits: dict[str, int] = {}
        merged_wins: dict[str, float] = {}
        total_iters = 0

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(type(self.validator), _get_validator_args(self.validator)),
        ) as executor:
            futures = {
                executor.submit(_run_mcts_worker, task): task
                for task in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                worker_visits, worker_wins, worker_iters = future.result()
                total_iters += worker_iters
                for move_id, count in worker_visits.items():
                    merged_visits[move_id] = merged_visits.get(move_id, 0) + count
                    merged_wins[move_id] = merged_wins.get(move_id, 0.0) + worker_wins.get(move_id, 0.0)

        # Find the best move by visit count
        if not merged_visits:
            # Fallback: no children expanded — pick first legal move
            root_state = self._clone_state(state)
            root_state["current_player_index"] = self._find_player_index(root_state, player_id)
            legal_moves = self.validator.get_legal_moves(root_state, player_id)
            best_move = legal_moves[0] if legal_moves else {}
            return MCTSResult(
                move=best_move,
                visit_count=0,
                win_rate=0.0,
                total_iterations=total_iters,
                search_time_ms=0.0,
            )

        best_move_id = max(merged_visits, key=merged_visits.get)
        best_visits = merged_visits[best_move_id]
        best_wins = merged_wins.get(best_move_id, 0.0)

        # Reconstruct the move dict from the original legal moves
        root_state = self._clone_state(state)
        root_state["current_player_index"] = self._find_player_index(root_state, player_id)
        legal_moves = self.validator.get_legal_moves(root_state, player_id)
        best_move = next((m for m in legal_moves if m.get("move_id") == best_move_id), {})

        # Collect top move stats for logging
        sorted_moves = sorted(merged_visits.items(), key=lambda x: x[1], reverse=True)
        top_moves = []
        for move_id, visits in sorted_moves[:5]:
            wins = merged_wins.get(move_id, 0.0)
            win_rate = wins / visits if visits > 0 else 0.0
            move_label = move_id.split("_", 1)[-1] if move_id else ""
            top_moves.append({
                "move": move_label,
                "visits": visits,
                "win_rate": round(win_rate, 3),
            })

        return MCTSResult(
            move=best_move,
            visit_count=best_visits,
            win_rate=best_wins / best_visits if best_visits > 0 else 0.0,
            total_iterations=total_iters,
            search_time_ms=0.0,
            top_moves=top_moves,
        )

    # ── Selection ────────────────────────────────────────────────────

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Traverse tree using UCT until we find an expandable or terminal node."""
        while node.is_fully_expanded() and not node.is_terminal():
            node = node.best_child(self.config.exploration_constant)
        return node

    # ── Expansion ────────────────────────────────────────────────────

    def _weighted_choice(self, moves: list[dict[str, Any]], weights: list[float]) -> dict[str, Any]:
        """Select a move weighted by prior values.

        Higher-weighted moves are more likely to be selected.
        Negative weights are clamped to 0.
        """
        if not moves:
            return {}

        if not weights or all(w == 0.0 for w in weights):
            return self.rng.choice(moves)

        # Clamp negatives to 0
        clamped = [max(0.0, w) for w in weights]

        # Debug: show what weights are being applied to each move
        debug_pairs = list(zip([m.get("action", m.get("card", str(m))) for m in moves], clamped))
        print(f"  [WEIGHT_DEBUG] {debug_pairs}")

        # If all zero after clamp, fall back to uniform
        total = sum(clamped)
        if total <= 0:
            return self.rng.choice(moves)

        # Weighted random selection using cumulative distribution
        r = self.rng.random() * total
        cumulative = 0.0
        for move, w in zip(moves, clamped):
            cumulative += w
            if r <= cumulative:
                return move

        return moves[-1]

    def _expand(self, node: MCTSNode) -> MCTSNode:
        """Pop an untried move using expansion weights, apply it, and create a child node."""
        # Use expansion weights from validator to filter/weight moves
        current_player = self._current_player_id(node.state)
        exp_weights = self.validator.expansion_weights(node.state, current_player, node.untried_moves)
        
        # Filter out moves with weight 0 and build weight list
        filtered_moves = []
        weights = []
        for m in node.untried_moves:
            w = exp_weights.get(m.get("move_id", ""), 0.0)
            if w > 0:
                filtered_moves.append(m)
                weights.append(w)
        
        # Fallback to all untried moves if filtering removed everything
        if not filtered_moves:
            filtered_moves = node.untried_moves
            weights = [node.priors.get(m.get("move_id", ""), 0.0) for m in filtered_moves]
        
        move = self._weighted_choice(filtered_moves, weights)
        node.untried_moves.remove(move)

        new_state = self._apply_move_to_state(node.state, move)

        current_player = self._current_player_id(new_state)
        turn_number = new_state.get("game_data", {}).get("round", 0)
        legal_moves = self.validator.get_legal_moves(new_state, current_player)
        child_priors = self.validator.prior_moves(new_state, current_player, legal_moves, turn_number)

        child = MCTSNode(
            state=new_state,
            move=move,
            parent=node,
            untried_moves=list(legal_moves),
            player_just_moved=self._current_player_id(node.state),
            priors=child_priors,
        )
        node.children.append(child)
        return child

    # ── Simulation ───────────────────────────────────────────────────

    def _simulate(self, node: MCTSNode, searching_player: str) -> tuple[float, bool]:
        """Random rollout from node's state. Returns (reward, finished_round)."""
        state = self._clone_state(node.state)
        current_player = self._current_player_id(state)
        original_player = searching_player

        for depth in range(self.config.max_depth):
            winner = self.validator.check_win(state)
            if winner is not None:
                return (1.0 if winner == original_player else 0.0), True

            if self.validator.stop_rollout(state, current_player):
                return (1.0 if original_player != current_player else 0.0), True

            moves = self.validator.get_legal_moves(state, current_player)
            if not moves:
                return (1.0 if original_player != current_player else 0.0), True

            move = self.rng.choice(moves)
            state = self._apply_move_to_state(state, move)
            current_player = self._current_player_id(state)

        return 0.5, False  # depth limit reached

    # ── Backpropagation ──────────────────────────────────────────────

    def _backpropagate(self, node: MCTSNode, reward: float, searching_player: str) -> None:
        """Walk back to root, incrementing visits and adding perspective-aware rewards."""
        current: MCTSNode | None = node
        while current is not None:
            current.visits += 1
            if current.player_just_moved == searching_player:
                current.wins += reward
            else:
                current.wins += (1.0 - reward)
            current = current.parent

    # ── State helpers ────────────────────────────────────────────────

    def _clone_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Deep copy a state dict for safe mutation."""
        return copy.deepcopy(state)

    def _apply_move_to_state(
        self, state: dict[str, Any], move: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply a move to a state dict, syncing current_player_index from game_data."""
        new_state = self._clone_state(state)

        result = self.validator.apply_move(new_state, move)
        new_state["game_data"] = result.get("game_data", new_state.get("game_data", {}))

        if "players" not in new_state:
            new_state["players"] = state.get("players", [])
        if "current_player_index" not in new_state:
            new_state["current_player_index"] = state.get("current_player_index", 0)

        # Sync current_player_index from game_data["current_player"]
        # The validator already handles player switching correctly
        game_data = new_state.get("game_data", {})
        current_player_id = game_data.get("current_player")
        if current_player_id:
            players = new_state.get("players", [])
            for i, p in enumerate(players):
                if p.get("player_id") == current_player_id:
                    new_state["current_player_index"] = i
                    break

        return new_state

    def _current_player_id(self, state: dict[str, Any]) -> str:
        """Return the player_id of the current player from game_data."""
        game_data = state.get("game_data", {})
        return game_data.get("current_player", "")

    def _find_player_index(self, state: dict[str, Any], player_id: str) -> int:
        """Find the index of *player_id* in the players list."""
        players = state.get("players", [])
        for i, p in enumerate(players):
            if p.get("player_id") == player_id:
                return i
        return 0

    def _get_opponent(self, player_id: str) -> str:
        """Return the opponent's player_id (assumes 2-player game)."""
        return "player_2" if player_id == "player_1" else "player_1"


# ── Worker helpers for parallel search ──────────────────────────────

# Module-level globals for worker processes (set by _init_worker)
_worker_validator: LegalMoveValidator | None = None


def _init_worker(validator_class: type, validator_args: tuple) -> None:
    """Initialize a worker process with its own validator instance."""
    global _worker_validator
    _worker_validator = validator_class(*validator_args)


def _get_validator_args(validator: LegalMoveValidator) -> tuple:
    """Extract constructor args from a validator instance.

    By convention, validators store their init args. If not available,
    returns empty tuple (assumes no-arg constructor).
    """
    if hasattr(validator, "_mcts_init_args"):
        return validator._mcts_init_args
    return ()


def _run_mcts_worker(
    task: tuple,
) -> tuple[dict[str, int], dict[str, float], int]:
    """Run an independent MCTS search in a worker process.

    Returns:
        (visit_counts, win_sums, iterations) for the root-level children.
    """
    state, player_id, config_dict, iterations, engine_class_name = task
    config = MCTSConfig(**config_dict)

    if engine_class_name == "MCTSEngineV2":
        from app.core.mcts_v2 import MCTSEngineV2
        engine = MCTSEngineV2(_worker_validator, config)
    else:
        engine = MCTSEngine(_worker_validator, config)

    root_state = engine._clone_state(state)
    root_state["current_player_index"] = engine._find_player_index(root_state, player_id)

    game_data = root_state.get("game_data", {})
    turn_number = game_data.get("round", 0)

    legal_moves = _worker_validator.get_legal_moves(root_state, player_id)
    # Apply game-specific move filters (turn-1-2 only)
    legal_moves = _worker_validator.filter_moves(root_state, player_id, legal_moves, turn_number)
    # Compute priors for root-level moves
    root_priors = _worker_validator.prior_moves(root_state, player_id, legal_moves, turn_number)

    root = MCTSNode(
        state=root_state,
        move=None,
        parent=None,
        untried_moves=list(legal_moves),
        player_just_moved=engine._get_opponent(player_id),
        priors=root_priors,
    )

    for _ in range(iterations):
        node = engine._select(root)
        if not node.is_terminal() and not node.is_fully_expanded():
            node = engine._expand(node)
        reward, _finished = engine._simulate(node, player_id)
        engine._backpropagate(node, reward, player_id)

    # Return visit counts and win sums for root-level children
    visit_counts = {}
    win_sums = {}
    for child in root.children:
        if child.move is not None:
            move_id = child.move.get("move_id", "")
            visit_counts[move_id] = child.visits
            win_sums[move_id] = child.wins

    return visit_counts, win_sums, iterations
