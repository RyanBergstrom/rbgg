from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.mcts import MCTSConfig


class IllegalMoveError(Exception):
    """Raised when a proposed move is illegal according to the game rules."""

    def __init__(self, message: str, move: Any | None = None) -> None:
        self.message = message
        self.move = move
        super().__init__(self.message)


class ValidatorConsistencyError(Exception):
    """Raised when a validator's internal state is inconsistent."""

    def __init__(self, message: str, validator_name: str | None = None) -> None:
        self.message = message
        self.validator_name = validator_name
        super().__init__(self.message)


class LegalMoveValidator(ABC):
    """Abstract base class for game move validation.

    Subclasses must implement all abstract methods to define game-specific
    rules. The ``recommend_ai_move`` method provides a default implementation
    that can be overridden for custom AI logic.

    State convention:
        All methods receive ``state`` as a dict with at minimum:
        - ``game_data: dict`` — game-specific board/piece state
        - ``players: list[dict]`` — player info list
        - ``current_player_index: int`` — whose turn it is

        Methods return dicts in the same shape, with ``game_data`` updated.
    """

    @abstractmethod
    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        """Return True if *move* is legal in *state*, False otherwise.

        Args:
            state: Current game state dict.
            move: A proposed move dict (must contain at least ``move_id``).
        """
        ...

    @abstractmethod
    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        """Return all legal moves for *player_id* in *state*.

        Each returned dict should be a complete move payload suitable for
        passing to ``validate_move`` and ``apply_move``.

        Args:
            state: Current game state dict.
            player_id: The player whose moves to enumerate.
        """
        ...

    @abstractmethod
    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        """Apply *move* to *state* and return the new state dict.

        The returned dict must include ``game_data`` with the updated
        game-specific state.  Turn switching (current_player_index)
        is handled by the caller (routes/engine).

        Args:
            state: Current game state dict.
            move: A validated move dict.
        """
        ...

    @abstractmethod
    def check_win(self, state: dict[str, Any]) -> str | None:
        """Check if the game is over in *state*.

        Returns:
            The ``player_id`` of the winner, or ``None`` if the game
            is still in progress.
        """
        ...

    def stop_rollout(self, state: dict[str, Any], player_id: str) -> bool:
        """Check if an MCTS rollout should stop early.

        Called during random rollouts (not the real game) to decide when
        to terminate the rollout and evaluate the position.  This is
        separate from ``check_win`` which determines the actual game
        outcome — ``stop_rollout`` gives games control over how deep
        rollouts go without affecting real game logic.

        Default returns False (rollout runs until ``check_win`` fires or
        ``max_depth`` is hit).

        Args:
            state: Current game state dict.
            player_id: The player whose turn it is.

        Returns:
            True if the rollout should stop here.
        """
        return False

    def recommend_ai_move(self, state: dict[str, Any], candidate_moves: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Pick a move from *candidate_moves* for the AI player.

        Default implementation returns the first candidate. Subclasses
        should override for smarter AI.

        Args:
            state: Current game state dict.
            candidate_moves: Legal moves to choose from.

        Returns:
            The chosen move dict, or ``None`` if no candidates.
        """
        if not candidate_moves:
            return None
        return candidate_moves[0]

    def filter_moves(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
        turn: int,
    ) -> list[dict[str, Any]]:
        """Remove moves that should never be considered by MCTS.

        Called before MCTS search to prune provably bad moves from the
        root legal moves list.  Default returns all moves unchanged.

        Args:
            state: Current game state dict.
            player_id: The player whose moves to filter.
            moves: Legal moves from ``get_legal_moves``.
            turn: Current turn number (0-indexed).

        Returns:
            Filtered list of moves.
        """
        return moves

    def prior_moves(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
        turn: int,
    ) -> dict[str, float]:
        """Assign soft preference values to moves for MCTS expansion ordering.

        Called during tree expansion to bias which moves get explored first.
        Higher values are explored earlier.  The bonus decays with visit
        count so rollout data eventually dominates.

        Default returns 0.0 for all moves (no preference).

        Args:
            state: Current game state dict.
            player_id: The player whose moves to score.
            moves: Legal moves available at this node.
            turn: Current turn number (0-indexed).

        Returns:
            Dict mapping move_id to a prior value (typically -1.0 to +1.0).
        """
        return {m.get("move_id", ""): 0.0 for m in moves}

    def expansion_weights(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Return weights for expansion move selection.

        Called during tree expansion to bias which untried moves get
        expanded first.  Higher weights = higher chance of expansion.
        Moves with weight 0 are excluded from expansion.

        Unlike ``prior_moves`` (which decays with visit count), these
        weights are applied once at expansion time to filter/weight
        the initial move selection.

        Default returns 1.0 for all moves (no filtering).

        Args:
            state: Current game state dict.
            player_id: The player whose moves to score.
            moves: Legal moves available at this node.

        Returns:
            Dict mapping move_id to a weight (0.0 = exclude, >0 = include).
        """
        return {m.get("move_id", ""): 1.0 for m in moves}

    def score_moves(
        self,
        state: dict[str, Any],
        player_id: str,
        moves: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Score each legal move for weighted rollout selection.

        Called during MCTS rollouts to bias move selection toward
        higher-value moves instead of uniform random.  The engine
        normalizes scores to a probability distribution.

        Default returns uniform scores (equal probability).

        Args:
            state: Current game state dict.
            player_id: The player whose moves to score.
            moves: Legal moves available.

        Returns:
            Dict mapping move_id to a raw score (higher = better).
        """
        return {m.get("move_id", ""): 1.0 for m in moves}

    def ai_config(self) -> "MCTSConfig | None":
        """Return MCTS configuration for this game, or None to use default AI.

        Subclasses should override to enable MCTS with game-appropriate
        tuning parameters (iterations, max_depth, etc.).  When this
        returns a non-None value, the AI move route will use MCTS instead
        of ``recommend_ai_move``.

        Returns:
            An ``MCTSConfig`` instance, or ``None`` to fall back to the
            default ``recommend_ai_move`` heuristic.
        """
        return None

    def initial_game_data(self) -> dict[str, Any]:
        """Return the initial game_data dict for a new game session.

        Subclasses should override to provide game-specific starting state
        (e.g., initial board layout).  Default returns an empty dict.
        """
        return {}

    def serialize_for_screen(self, game_data: dict[str, Any]) -> dict[str, Any]:
        """Convert game_data to a format suitable for the screen state.

        Called by GameEngine.build_screen_state() to overlay game-specific
        data onto the config-defined components.  The returned dict is
        merged into the screen state as ``game_data``.

        Default implementation returns game_data as-is.  Subclasses
        should override to provide richer screen-ready data (e.g.,
        converting a board array to cells with piece info).
        """
        return game_data
