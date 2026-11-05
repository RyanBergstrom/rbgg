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
import json
import math
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.legal_move_interface import LegalMoveValidator
from app.core.log import suppress_tracing, trace
from app.core.search_policy import SearchPolicy, ValidatorSearchPolicy, policy_for_validator


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
    strategy: str = "legacy"  # "legacy" or "hybrid"
    hot_pool_size: int = 3
    admission_interval: int = 15
    root_score_margin: float = 0.10
    root_min_actions: int = 5
    final_budget_fraction: float = 0.05
    confidence_constant: float = 0.15
    discard_ceiling: float = 0.40
    diagnostic_enabled: bool = False
    diagnostic_max_records: int = 100
    diagnostic_extremes_per_root: int = 5


@dataclass
class MCTSResult:
    """Output of an MCTS search."""

    move: dict[str, Any] | None
    visit_count: int
    win_rate: float
    total_iterations: int
    search_time_ms: float
    top_moves: list[dict[str, Any]] = field(default_factory=list)
    finished_rounds: int = 0
    depth_limited: int = 0
    max_depth_reached: int = 0
    average_depth: float = 0.0
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    diagnostic_summaries: list[dict[str, Any]] = field(default_factory=list)


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
    hot_pool: list[dict[str, Any]] | None = None
    cold_pool: list[dict[str, Any]] | None = None
    action_values: dict[str, float] = field(default_factory=dict)

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

    Works with any ``LegalMoveValidator`` through the policy contract.

    When ``config.workers > 1``, uses root parallelism: independent MCTS
    searches run in parallel via ``ProcessPoolExecutor``, and visit counts
    are merged to select the best move.
    """

    def __init__(
        self,
        validator: LegalMoveValidator,
        config: MCTSConfig | None = None,
        policy: SearchPolicy | None = None,
    ) -> None:
        self.validator = validator
        self.config = config or MCTSConfig()
        self.rng = random.Random(self.config.seed)
        self.policy: SearchPolicy = policy or policy_for_validator(validator)

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
            if self.config.strategy == "hybrid":
                result = HybridMCTSEngine(self.validator, self.config, self.policy)._search(state, player_id)
            elif self.config.workers > 1:
                result = self._search_parallel(state, player_id)
            else:
                result = self._search_sequential(state, player_id)

        result.search_time_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Log summary (outside suppress_tracing so it actually logs)
        move = result.move or {}
        trace(
            "mcts",
            "search_result",
            player_id=player_id,
            iterations=result.total_iterations,
            best_move=move.get("type", "") + ":" + move.get("card", move.get("source", "")),
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

        turn_number = root_state.get("game_data", {}).get("round", 0)
        legal_moves = self.policy.filter_moves(
            root_state, player_id, self.policy.legal_moves(root_state, player_id), turn_number
        )
        root_priors = self.policy.prior_moves(root_state, player_id, legal_moves, turn_number)

        root = MCTSNode(
            state=root_state,
            move=None,
            parent=None,
            untried_moves=list(legal_moves),
            player_just_moved=self.policy.opponent_player(root_state, player_id),
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
                    "full_game_rollout": self.config.full_game_rollout,
                },
                worker_iters,
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
            legal_moves = self.policy.legal_moves(root_state, player_id)
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
        legal_moves = self.policy.legal_moves(root_state, player_id)
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
        exp_weights = self.policy.expansion_weights(node.state, current_player, node.untried_moves)
        
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
        legal_moves = self.policy.legal_moves(new_state, current_player)
        child_priors = self.policy.prior_moves(new_state, current_player, legal_moves, turn_number)

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
        """Run a heuristic-weighted rollout and return its score reward.

        This combines the strongest behavior from the former engine versions:
        V3's heuristic rollout selection takes precedence over V1's uniform
        random selection, while V2's score-differential evaluation takes
        precedence over V1's binary winner reward.
        """
        state = self._clone_state(node.state)
        current_player = self._current_player_id(state)

        depth_limit = 200 if self.config.full_game_rollout else self.config.max_depth
        for _ in range(depth_limit):
            if self.policy.is_terminal(state):
                return self._score_reward(state, searching_player), True

            if self.policy.stop_rollout(state, current_player):
                return self._score_reward(state, searching_player), True

            moves = self.policy.legal_moves(state, current_player)
            if not moves:
                return self._score_reward(state, searching_player), True

            scores = self.policy.score_moves(state, current_player, moves)
            weights = [scores.get(m.get("move_id", ""), 0.0) for m in moves]
            move = self._weighted_choice(moves, weights)
            state = self._apply_move_to_state(state, move)
            current_player = self._current_player_id(state)

        return self._score_reward(state, searching_player), False

    def _score_reward(
        self,
        state: dict[str, Any],
        searching_player: str,
        winner: str | None = None,
    ) -> float:
        """Delegate legacy reward evaluation to the selected policy."""
        return self.policy.score_reward(state, searching_player, winner)

    # ── Backpropagation ──────────────────────────────────────────────

    def _backpropagate(self, node: MCTSNode, reward: float, searching_player: str) -> None:
        """Backpropagate the V2 perspective-aware score reward."""
        current: MCTSNode | None = node
        while current is not None:
            current.visits += 1
            if current.player_just_moved == searching_player:
                current.wins += reward
            else:
                current.wins -= reward
            current = current.parent

    # ── State helpers ────────────────────────────────────────────────

    def _clone_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Deep copy a state dict for safe mutation."""
        return copy.deepcopy(state)

    def _apply_move_to_state(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        """Apply a simulated move through the selected search policy."""
        return self.policy.apply_move(state, move)

    def _current_player_id(self, state: dict[str, Any]) -> str:
        """Return the current player from game data or the generic state index."""
        return self.policy.current_player(state)

    def _find_player_index(self, state: dict[str, Any], player_id: str) -> int:
        """Find the index of *player_id* in the players list."""
        players = state.get("players", [])
        for i, p in enumerate(players):
            if p.get("player_id") == player_id:
                return i
        return 0

    def _get_opponent(self, player_id: str) -> str:
        """Preserve the legacy helper API for two-player callers."""
        opponent = self.policy.opponent_player(
            {"players": [{"player_id": player_id}, {"player_id": "player_2" if player_id == "player_1" else "player_1"}]},
            player_id,
        )
        return opponent or player_id

def _canonical_move_id(move: dict[str, Any]) -> str:
    """Return a deterministic identity for a legal move."""
    move_id = move.get("move_id")
    if move_id is not None:
        return str(move_id)
    return json.dumps(move, sort_keys=True, separators=(",", ":"), default=str)


def _validate_hybrid_value(value: Any, label: str) -> float:
    """Validate the hybrid engine's root-perspective [0, 1] contract."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a numeric value in [0, 1]")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be a numeric value in [0, 1]")
    return value


class HybridMCTSEngine:
    """Deterministic, pruned, horizon-bounded search with no rollouts."""

    def __init__(self, validator: LegalMoveValidator, config: MCTSConfig, policy: SearchPolicy | None = None) -> None:
        self.validator = validator
        self.config = config
        self._adapter = MCTSEngine(validator, config, policy)
        self.policy = policy or self._adapter.policy

        if config.iterations <= 0:
            raise ValueError("iterations must be greater than zero")
        if config.diagnostic_max_records < 0:
            raise ValueError("diagnostic_max_records must not be negative")
        if config.diagnostic_extremes_per_root < 1:
            raise ValueError("diagnostic_extremes_per_root must be positive")
        if config.max_depth < 1 or config.hot_pool_size < 1 or config.admission_interval < 1:
            raise ValueError("max_depth, hot_pool_size, and admission_interval must be positive")
        if config.root_score_margin < 0.0:
            raise ValueError("root_score_margin must not be negative")
        if config.root_min_actions < 1:
            raise ValueError("root_min_actions must be positive")
        if config.exploration_constant <= 0:
            raise ValueError("exploration_constant must be positive")
        if config.confidence_constant < 0:
            raise ValueError("confidence_constant must not be negative")
        if not 0.0 < config.discard_ceiling <= 1.0:
            raise ValueError("discard_ceiling must be greater than zero and at most one")
        if not 0 < config.final_budget_fraction < 1:
            raise ValueError("final_budget_fraction must be between zero and one")

    def _initialize_pools(
        self,
        node: MCTSNode,
        state: dict[str, Any],
        root_player_id: str,
    ) -> None:
        if node.hot_pool is not None:
            return

        actor_id = self.policy.current_player(state)
        legal = list(self.policy.legal_moves(state, actor_id))
        viable = [
            move for move in legal
            if not self.policy.is_dominated_action(state, move, root_player_id)
        ]
        if viable:
            legal = viable
        ids = [_canonical_move_id(move) for move in legal]
        if len(ids) != len(set(ids)):
            raise ValueError("legal moves contain duplicate canonical move IDs")

        scored: list[tuple[float, str, dict[str, Any]]] = []
        ranking_scores: dict[str, float] = {}
        for move, move_id in zip(legal, ids):
            next_state = self.policy.apply_move(state, move)
            value = _validate_hybrid_value(
                self.policy.one_ply_value(
                    state, move, next_state, root_player_id
                ),
                "one_ply_value",
            )
            node.action_values[move_id] = value
            scored.append((value, move_id, move))
        adjusted = self.policy.adjust_action_values(
            state,
            legal,
            {move_id: value for value, move_id, _ in scored},
            root_player_id,
        )
        scored = [
            (adjusted.get(move_id, value), move_id, move)
            for value, move_id, move in scored
        ]
        for value, move_id, _ in scored:
            node.action_values[move_id] = value

        # Policy-specific optimistic bounds do not delete a move; they only
        # decide whether it starts in the hot pool or waits for admission.
        # This lets clearly hopeless branches consume very few iterations
        # while preserving hidden-information surprises for later exploration.
        bound_callback = getattr(self.policy, "optimistic_action_bound", None)
        if bound_callback is not None:
            for value, move_id, move in scored:
                ranking_scores[move_id] = min(
                    value,
                    _validate_hybrid_value(
                        bound_callback(state, move, self.policy.apply_move(state, move), root_player_id),
                        "optimistic_action_bound",
                    ),
                )
        else:
            ranking_scores = {move_id: value for value, move_id, _ in scored}

        if node.parent is None and scored:
            best_score = max(ranking_scores.values())
            threshold = best_score - self.config.root_score_margin
            retained = [
                item for item in scored
                if ranking_scores[item[1]] >= threshold
            ]
            # Keep a small safety set and preserve both strategic action
            # classes when available, even if their immediate score is lower.
            ranked = sorted(scored, key=lambda item: (-ranking_scores[item[1]], item[1]))
            for item in ranked[: self.config.root_min_actions]:
                if item not in retained:
                    retained.append(item)
            for action_type in ("play_expedition", "discard"):
                candidate = next((item for item in ranked if item[2].get("type") == action_type), None)
                if candidate is not None and candidate not in retained:
                    retained.append(candidate)
            scored = retained
            legal = [item[2] for item in scored]

        k = min(self.config.hot_pool_size, len(legal))
        if len(legal) <= self.config.hot_pool_size:
            node.hot_pool = [item[2] for item in sorted(scored, key=lambda item: (-ranking_scores.get(item[1], item[0]), item[1]))]
            node.cold_pool = []
            return
        scored.sort(key=lambda item: (-ranking_scores.get(item[1], item[0]), item[1]))
        node.hot_pool = [item[2] for item in scored[:k]]
        node.cold_pool = [item[2] for item in scored[k:]]

    def _existing_ids(self, node: MCTSNode) -> set[str]:
        return {_canonical_move_id(child.move or {}) for child in node.children}

    def _next_action(
        self,
        node: MCTSNode,
        state: dict[str, Any],
        root_player_id: str,
        force_fallback: bool,
    ) -> dict[str, Any] | None:
        self._initialize_pools(node, state, root_player_id)
        hot = node.hot_pool or []
        cold = node.cold_pool or []
        existing = self._existing_ids(node)

        for move in hot:
            if _canonical_move_id(move) not in existing:
                return move

        if cold and node.visits > 0 and (
            node.visits % self.config.admission_interval == 0 or force_fallback
        ):
            promoted = cold.pop(0)
            hot.append(promoted)
            return promoted
        return None

    def _has_expandable(
        self,
        node: MCTSNode,
        state: dict[str, Any],
        root_player_id: str,
        force_fallback: bool,
    ) -> bool:
        self._initialize_pools(node, state, root_player_id)
        existing = self._existing_ids(node)
        if any(_canonical_move_id(move) not in existing for move in (node.hot_pool or [])):
            return True
        admission_tick = node.visits > 0 and node.visits % self.config.admission_interval == 0
        return bool(node.cold_pool and (force_fallback or admission_tick))

    def _ucb_child(self, node: MCTSNode) -> MCTSNode:
        parent_visits = max(1, node.visits)

        def key(child: MCTSNode) -> tuple[float, str]:
            if child.visits == 0:
                score = float("inf")
            else:
                score = (child.wins / child.visits) + self.config.exploration_constant * math.sqrt(
                    math.log(parent_visits) / child.visits
                )
            return score, _canonical_move_id(child.move or {})

        return max(node.children, key=key)

    def _search(self, state: dict[str, Any], root_player_id: str) -> MCTSResult:
        root_state = self._adapter._clone_state(state)
        root_state["current_player_index"] = self._adapter._find_player_index(
            root_state, root_player_id
        )
        root = MCTSNode(state=root_state, move=None, parent=None)
        start = time.perf_counter()
        forced_phase = max(0, int(self.config.iterations * (1 - self.config.final_budget_fraction)))
        depth_total = 0
        deepest = 0
        diagnostics: list[dict[str, Any]] = []
        diagnostic_by_root: dict[str, list[dict[str, Any]]] = {}

        if self.policy.is_terminal(root_state):
            return MCTSResult(None, 0, self.policy.terminal_reward(root_state, root_player_id), 0, 0.0)

        for iteration in range(self.config.iterations):
            node = root
            sim_state = self._adapter._clone_state(root_state)
            path = [root]
            depth = 0
            forced_used = False

            while node.children and depth < self.config.max_depth and not self.policy.is_terminal(sim_state):
                force = iteration >= forced_phase and not forced_used
                if self._has_expandable(node, sim_state, root_player_id, force):
                    break
                node = self._ucb_child(node)
                sim_state = self._adapter._clone_state(node.state)
                path.append(node)
                depth += 1

            if depth < self.config.max_depth and not self.policy.is_terminal(sim_state):
                force = iteration >= forced_phase and not forced_used
                hot_ids_before = {
                    _canonical_move_id(move) for move in (node.hot_pool or [])
                }
                action = self._next_action(node, sim_state, root_player_id, force)
                if action is not None:
                    if force and _canonical_move_id(action) not in hot_ids_before:
                        forced_used = True
                    next_state = self.policy.apply_move(sim_state, action)
                    child = MCTSNode(next_state, action, node)
                    node.children.append(child)
                    node = child
                    sim_state = next_state
                    path.append(node)
                    depth += 1

            if self.policy.is_terminal(sim_state):
                value = _validate_hybrid_value(
                    self.policy.terminal_reward(sim_state, root_player_id),
                    "terminal_reward",
                )
            else:
                value = _validate_hybrid_value(
                    self.policy.horizon_value(sim_state, root_player_id),
                    "horizon_value",
                )
            if self.config.diagnostic_enabled:
                record: dict[str, Any] = {
                    "depth": depth,
                    "path": [
                        {
                            "move_id": _canonical_move_id(visited.move or {}),
                            "action": copy.deepcopy(visited.move),
                        }
                        for visited in path[1:]
                    ],
                    "leaf_type": "terminal" if self.policy.is_terminal(sim_state) else "horizon",
                    "value": value,
                }
                if record["leaf_type"] == "horizon":
                    explain = getattr(self.policy, "explain_horizon", None)
                    if explain is not None:
                        record["horizon"] = explain(sim_state, root_player_id)
                root_move_id = record["path"][0]["move_id"] if record["path"] else "__root__"
                bucket = diagnostic_by_root.setdefault(root_move_id, [])
                bucket.append(record)
                limit = self.config.diagnostic_extremes_per_root
                if limit > 0 and len(bucket) > limit * 2:
                    ordered_bucket = sorted(bucket, key=lambda item: item["value"], reverse=True)
                    bucket[:] = ordered_bucket[:limit] + ordered_bucket[-limit:]
            for visited in path:
                visited.visits += 1
                visited.wins += value
            depth_total += depth
            deepest = max(deepest, depth)

        if not root.children:
            return MCTSResult(None, 0, 0.5, self.config.iterations, round((time.perf_counter() - start) * 1000, 2))

        if self.config.diagnostic_enabled:
            diagnostics = []
            for bucket in diagnostic_by_root.values():
                ordered_bucket = sorted(bucket, key=lambda item: item["value"], reverse=True)
                extremes = ordered_bucket[: self.config.diagnostic_extremes_per_root]
                seen = {id(item) for item in extremes}
                extremes.extend(
                    item for item in ordered_bucket[-self.config.diagnostic_extremes_per_root :]
                    if id(item) not in seen
                )
                diagnostics.extend(extremes)
            if self.config.diagnostic_max_records < len(diagnostics):
                diagnostics = diagnostics[: self.config.diagnostic_max_records]

        def raw_selection_key(child: MCTSNode) -> tuple[float, float, int, str]:
            average_value = child.wins / child.visits if child.visits else 0.0
            if child.move and child.move.get("type") == "discard":
                # The discard ceiling applies after all deeper horizon values
                # have been accumulated. A discard may be useful, but it can
                # never become artificially lucrative through repeated safe
                # leaf evaluations.
                average_value = min(average_value, self.config.discard_ceiling)
            if child.visits:
                uncertainty = self.config.confidence_constant * math.sqrt(
                    math.log(max(1, root.visits)) / child.visits
                )
            else:
                uncertainty = float("inf")
            lower_confidence_value = average_value - uncertainty
            return (
                lower_confidence_value,
                average_value,
                child.visits,
                _canonical_move_id(child.move or {}),
            )

        acceptable_play_scores = [
            raw_selection_key(child)[0]
            for child in root.children
            if child.move and child.move.get("type") == "play_expedition"
            and root.action_values.get(_canonical_move_id(child.move), 0.0) >= 0.25
        ]
        best_acceptable_play_score = max(acceptable_play_scores, default=None)

        def final_selection_key(child: MCTSNode) -> tuple[float, float, int, str]:
            score, average, visits, move_id = raw_selection_key(child)
            if (
                best_acceptable_play_score is not None
                and child.move
                and child.move.get("type") == "discard"
            ):
                relief_callback = getattr(self.policy, "discard_relief", None)
                relief = 0.0
                if relief_callback is not None:
                    relief = relief_callback(
                        root_state,
                        child.move,
                        self.policy.apply_move(root_state, child.move),
                        root_player_id,
                    )
                if relief < 0.05:
                    score = min(score, best_acceptable_play_score - 0.01)
            return score, average, visits, move_id

        best = max(root.children, key=final_selection_key)
        ordered = sorted(
            root.children,
            key=lambda child: (
                -final_selection_key(child)[0],
                -final_selection_key(child)[1],
                -child.visits,
                _canonical_move_id(child.move or {}),
            ),
        )
        top_moves = [
            {
                "move": _canonical_move_id(child.move or {}),
                "visits": child.visits,
                "win_rate": round(child.wins / child.visits, 3) if child.visits else 0.0,
                "one_ply_value": round(
                    root.action_values.get(_canonical_move_id(child.move or {}), 0.0),
                    3,
                ),
                "selection_score": round(final_selection_key(child)[0], 3),
            }
            for child in ordered
        ]
        diagnostic_summaries: list[dict[str, Any]] = []
        by_root: dict[str, list[dict[str, Any]]] = {}
        for record in diagnostics:
            path = record.get("path", [])
            if path:
                by_root.setdefault(path[0]["move_id"], []).append(record)
        for child in ordered:
            move_id = _canonical_move_id(child.move or {})
            samples = by_root.get(move_id, [])
            sample_values = [float(sample["value"]) for sample in samples]
            summary: dict[str, Any] = {
                "move": move_id,
                "selected": child is best,
                "visits": child.visits,
                "average_value": child.wins / child.visits if child.visits else 0.0,
                "selection_score": final_selection_key(child)[0],
                "one_ply_value": root.action_values.get(move_id, 0.0),
                "diagnostic_samples": len(samples),
            }
            ordered_samples = sorted(samples, key=lambda sample: float(sample["value"]), reverse=True)
            summary["top_paths"] = ordered_samples[:5]
            summary["bottom_paths"] = list(reversed(ordered_samples[-5:]))
            if sample_values:
                summary.update({
                    "sample_average": sum(sample_values) / len(sample_values),
                    "sample_min": min(sample_values),
                    "sample_max": max(sample_values),
                })
                horizon_samples = [sample.get("horizon", {}) for sample in samples if sample.get("horizon")]
                if horizon_samples:
                    for key in ("relative", "absolute", "latent_equity", "compound_setup", "final"):
                        values = [float(item[key]) for item in horizon_samples if key in item]
                        if values:
                            summary[f"average_{key}"] = sum(values) / len(values)
            diagnostic_summaries.append(summary)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        return MCTSResult(
            best.move,
            best.visits,
            best.wins / best.visits if best.visits else 0.0,
            self.config.iterations,
            elapsed,
            top_moves,
            max_depth_reached=deepest,
            average_depth=depth_total / self.config.iterations,
            diagnostics=diagnostics,
            diagnostic_summaries=diagnostic_summaries,
        )


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
    state, player_id, config_dict, iterations = task
    config = MCTSConfig(**config_dict)
    engine = MCTSEngine(_worker_validator, config)

    root_state = engine._clone_state(state)
    root_state["current_player_index"] = engine._find_player_index(root_state, player_id)

    policy = engine.policy
    turn_number = root_state.get("game_data", {}).get("round", 0)
    legal_moves = policy.filter_moves(
        root_state, player_id, policy.legal_moves(root_state, player_id), turn_number
    )
    root_priors = policy.prior_moves(root_state, player_id, legal_moves, turn_number)

    root = MCTSNode(
        state=root_state,
        move=None,
        parent=None,
        untried_moves=list(legal_moves),
        player_just_moved=policy.opponent_player(root_state, player_id),
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
