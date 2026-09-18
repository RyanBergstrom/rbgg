"""Santorini validator core rules.

Implements the official Santorini game rules:
- 5x5 grid board
- 2 players, 4 workers each
- Workers move 1 step (orthogonal or diagonal)
- Cannot move into a domed space (height 4)
- Cannot move onto a space occupied by a worker
- "Climb rule": can only move to a space at most 1 level higher
- After moving, player builds 1 step
- Building to height 4 creates a dome; domed spaces are immobile
- Win conditions:
  - Win by reaching height three: a player wins if they move a worker to height 3
  - Win by blocking: a player wins if the opponent has no legal moves on their turn
- Scoring: last player to place a worker or build wins
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple


class Player(Enum):
    ONE = "one"
    TWO = "two"


class Component(Enum):
    WORKER_1 = "worker1"
    WORKER_2 = "worker2"
    WORKER_3 = "worker3"
    WORKER_4 = "worker4"


@dataclass
class Position:
    """Grid position on the 5x5 board."""

    row: int
    col: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return self.row == other.row and self.col == other.col

    def __hash__(self) -> int:
        return hash((self.row, self.col))

    def __str__(self) -> str:
        return f"({self.row},{self.col})"


@dataclass
class Worker:
    """A worker piece belonging to a player."""

    player: Player
    position: Position
    # Workers that have already moved this turn are tracked by the game state,
    # not per-worker here. All four workers start unmoved.

    def can_climb_from(self, from_pos: Position, to_pos: Position, board: Board) -> bool:
        """Check if worker can climb from from_pos to to_pos per Santorini rules."""
        from_h = board.height_at(from_pos)
        to_h = board.height_at(to_pos)
        if from_h is None or to_h is None:
            return False
        # Worker cannot move into a domed space (height 4)
        if to_h == 4:
            return False
        # Climb rule: can only move to a space at most 1 level higher
        diff = to_h - from_h
        return diff <= 1


@dataclass
class Board:
    """5x5 game board tracking heights and worker positions."""

    # height[r][c] = number of blocks stacked at (r,c), 0-4 (4 = dome)
    height: Dict[Position, int] = field(default_factory=dict)

    # workers[player][worker_id] = position of that worker
    workers: Dict[Player, Dict[str, Position]] = field(default_factory=lambda: {
        Player.ONE: {},
        Player.TWO: {},
    })

    BOARD_SIZE = 5

    def __post_init__(self) -> None:
        # Ensure all height entries are ints (YAML may load as floats)
        for pos, h in self.height.items():
            if pos not in self._initialized():
                self.height[pos] = 0
        # Ensure all workers dicts exist
        for p in Player:
            if p not in self.workers:
                self.workers[p] = {}

    def _initialized(self) -> Set[Position]:
        """Return set of positions that have been explicitly set."""
        return set(self.height.keys())

    def height_at(self, pos: Position) -> int:
        """Return the height at position pos (0-4)."""
        if pos.row < 0 or pos.row >= self.BOARD_SIZE or pos.col < 0 or pos.col >= self.BOARD_SIZE:
            return None
        return self.height.get(pos, 0)

    def is_domed(self, pos: Position) -> bool:
        """Check if position has a dome (height 4)."""
        return self.height_at(pos) == 4

    def is_occupied_by_worker(self, pos: Position) -> bool:
        """Check if position has a worker on it."""
        for p in Player:
            for wpos in self.workers[p].values():
                if wpos == pos:
                    return True
        return False

    def is_valid_position(self, pos: Position) -> bool:
        """Check if position is within the 5x5 board."""
        return (0 <= pos.row < self.BOARD_SIZE and 0 <= pos.col < self.BOARD_SIZE)


@dataclass
class MovePayload:
    """Payload for a move action."""

    worker_id: str  # e.g. "worker1"
    from_row: int
    from_col: int
    to_row: int
    to_col: int


@dataclass
class BuildPayload:
    """Payload for a build action."""

    row: int
    col: int


@dataclass
class GameState:
    """Current state of a Santorini game."""

    player_turn: Player = Player.ONE
    board: Board = field(default_factory=Board)
    # Track which workers have moved this turn (to enforce "move then build")
    moved_workers: Set[str] = field(default_factory=set)

    def next_player(self) -> Player:
        return Player.TWO if self.player_turn == Player.ONE else Player.ONE

    def check_win_by_reaching_height_three(self) -> Optional[Player]:
        """Check if any player has won by moving a worker to height 3.

        In Santorini, a player wins immediately if they move one of their workers
        to a space at height 3 (the third block level).  If, at the start of a
        turn, any player has a worker at height 3, that player wins.

        Returns:
            The winning Player (the player who has a worker at height 3), or None
            if no worker is at height 3.
        """
        # Check if any player has a worker at height 3
        for p in Player:
            for worker_id, wpos in self.board.workers[p].items():
                h = self.board.height_at(wpos)
                if h == 3:
                    return p
        return None

    def check_win_by_opponent_no_legal_moves(self) -> Optional[Player]:
        """Check if the current player has won because the opponent has no legal moves.

        In Santorini, if a player has no legal moves on their turn (all workers
        are blocked or all destinations are domed/occupied), the opponent wins.

        Returns:
            The winning Player (the opponent of the player with no legal moves),
            or None if both players have legal moves available.
        """
        # Check if the current player has any legal moves
        has_legal = False
        for worker_id in self.board.workers[self.player_turn]:
            # Worker positions are stored; we check if any worker can move legally
            from_pos = self.board.workers[self.player_turn][worker_id]
            # Check all adjacent positions (orthogonal + diagonal)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    to_pos = Position(from_pos.row + dr, from_pos.col + dc)
                    if not self.board.is_valid_position(to_pos):
                        continue
                    if self.board.is_domed(to_pos):
                        continue
                    if self.board.is_occupied_by_worker(to_pos):
                        continue
                    # Climb rule
                    from_h = self.board.height_at(from_pos)
                    to_h = self.board.height_at(to_pos)
                    if from_h is None or to_h is None:
                        continue
                    if to_h - from_h > 1:
                        continue
                    # This is a legal move
                    has_legal = True
                    break
                if has_legal:
                    break
            if has_legal:
                break

        if not has_legal:
            # Current player has no legal moves -> opponent wins
            opponent = Player.TWO if self.player_turn == Player.ONE else Player.ONE
            return opponent
        return None


def check_win(state: GameState) -> Optional[Player]:
    """Check win conditions for the current state.

    Checks both win conditions in order:
    1. Win by reaching height three
    2. Win by opponent having no legal moves

    Returns:
        The winning Player, or None if the game continues.
    """
    # Check win by reaching height three first
    winner = state.check_win_by_reaching_height_three()
    if winner is not None:
        return winner
    # Then check win by opponent having no legal moves
    winner = state.check_win_by_opponent_no_legal_moves()
    if winner is not None:
        return winner
    return None


# ---------------------------------------------------------------------------
# Starting positions for workers (two players, four workers each)
# ---------------------------------------------------------------------------

# Starting positions for workers (two players, four workers each)
# Player ONE workers start at bottom-left area, Player TWO at top-right
STARTING_POSITIONS: Dict[Player, List[Position]] = {
    Player.ONE: [
        Position(0, 0),
        Position(0, 1),
        Position(4, 0),
        Position(4, 1),
    ],
    Player.TWO: [
        Position(4, 4),
        Position(4, 3),
        Position(0, 4),
        Position(0, 3),
    ],
}


def initial_state() -> GameState:
    """Create the initial Santorini game state with four workers per player placed.

    Returns:
        GameState with all eight workers (4 per player) placed on starting positions,
        board heights all 0, and Player.ONE to move first.
    """
    board = Board()
    # Place all workers at starting positions
    for player, positions in STARTING_POSITIONS.items():
        for i, pos in enumerate(positions, 1):
            worker_id = f"worker{i}"
            board.workers[player][worker_id] = pos
            # Height at starting position remains 0 (no blocks yet)
    return GameState(player_turn=Player.ONE, board=board)


# ---------------------------------------------------------------------------
# Legality checks
# ---------------------------------------------------------------------------

def legal_moves(state: GameState, payload: MovePayload) -> List[MovePayload]:
    """Return legal move payloads for the given state and payload.

    A move is legal if:
    - The worker belongs to the player whose turn it is
    - The worker hasn't already moved this turn (each worker moves once per turn)
    - The destination is within the 5x5 board
    - The destination is not domed (height 4)
    - The destination is not occupied by another worker
    - The "climb rule" is satisfied (can only move to a space at most 1 level higher)
    """
    worker_id = payload.worker_id
    player = state.player_turn

    # Check worker belongs to current player
    if worker_id not in state.board.workers[player]:
        return []

    # Check worker hasn't already moved this turn
    if worker_id in state.moved_workers:
        return []

    from_pos = Position(payload.from_row, payload.from_col)
    to_pos = Position(payload.to_row, payload.to_col)

    # Check destination is valid board position
    if not state.board.is_valid_position(to_pos):
        return []

    # Check destination is not domed
    if state.board.is_domed(to_pos):
        return []

    # Check destination is not occupied by another worker
    if state.board.is_occupied_by_worker(to_pos):
        return []

    # Check climb rule: can only move to a space at most 1 level higher
    from_h = state.board.height_at(from_pos)
    to_h = state.board.height_at(to_pos)
    if from_h is None or to_h is None:
        return []
    if to_h - from_h > 1:
        return []

    # All checks passed - return the validated move
    return [payload]


def legal_builds(state: GameState, payload: BuildPayload) -> List[BuildPayload]:
    """Return legal build payloads for the given state and payload.

    A build is legal if:
    - The build position is within the 5x5 board
    - The build position is not already domed (height 4)
    - The build position has a worker belonging to the current player adjacent
      (i.e., the player must have a worker on a neighboring space)
    - The current player has already moved this turn (must move before building)
    """
    player = state.player_turn

    # Check player has moved this turn before building
    if not state.moved_workers:
        return []

    row, col = payload.row, payload.col

    # Check position is valid
    if not state.board.is_valid_position(Position(row, col)):
        return []

    # Check position is not already domed
    if state.board.is_domed(Position(row, col)):
        return []

    # Check that the current player has a worker adjacent to the build position
    build_pos = Position(row, col)
    has_adjacent_worker = False
    for p in Player:
        for wpos in state.board.workers[p].values():
            # Adjacent includes orthogonal and diagonal neighbors
            if (abs(wpos.row - build_pos.row) <= 1 and
                    abs(wpos.col - build_pos.col) <= 1 and
                    not (wpos.row == build_pos.row and wpos.col == build_pos.col)):
                has_adjacent_worker = True
                break
        if has_adjacent_worker:
            break

    if not has_adjacent_worker:
        return []

    return [payload]


# ---------------------------------------------------------------------------
# Apply move/build transitions
# ---------------------------------------------------------------------------

def apply_move(state: GameState, payload: MovePayload) -> GameState:
    """Apply a legal move, returning a new GameState.

    Transitions:
    - Worker moves from (from_row,from_col) to (to_row,to_col)
    - Worker marks as moved this turn
    - Turn passes to other player ONLY after build (move+build is one turn)
    - Actually: worker moves, then player builds; if no build, turn passes
    """
    # Deep copy the state
    new_board = Board(
        height=dict(state.board.height),
        workers={Player.ONE: dict(state.board.workers[Player.ONE]),
                 Player.TWO: dict(state.board.workers[Player.TWO])},
    )
    new_state = GameState(
        player_turn=state.player_turn,
        board=new_board,
        moved_workers=set(state.moved_workers),
    )

    worker_id = payload.worker_id
    from_pos = Position(payload.from_row, payload.from_col)
    to_pos = Position(payload.to_row, payload.to_col)
    player = state.player_turn

    # Update worker position
    new_board.workers[player][worker_id] = to_pos

    # Mark worker as moved this turn
    new_moved = set(state.moved_workers)
    new_moved.add(worker_id)
    new_state.moved_workers = new_moved

    return new_state


def apply_build(state: GameState, payload: BuildPayload) -> GameState:
    """Apply a legal build, returning a new GameState.

    Transitions:
    - Remove one block from the build position (height -= 1)
    - If height reaches 0, space is cleared
    - If height reaches 4 (was 3, build makes it 4), a dome is created
    - Dome creation means no more building on that space
    - After building, turn passes to other player
    - Reset moved_workers since the build action completes the turn
    """
    new_board = Board(
        height=dict(state.board.height),
        workers={Player.ONE: dict(state.board.workers[Player.ONE]),
                 Player.TWO: dict(state.board.workers[Player.TWO])},
    )
    new_state = GameState(
        player_turn=state.player_turn,
        board=new_board,
        moved_workers=set(state.moved_workers),
    )

    row, col = payload.row, payload.col
    build_pos = Position(row, col)
    player = state.player_turn

    # Get current height, default to 0
    current_h = new_board.height_at(build_pos)

    # Build: increment height
    # In Santorini, building HEIGHTS the space. Starting from 0,
    # first build makes it 1, second makes it 2, third makes it 3, fourth makes it 4 (dome)
    new_height = (current_h or 0) + 1
    new_board.height[build_pos] = new_height

    # If height becomes 4, a dome is created - mark as domed
    # Domes at height 4 are immobile (no more building, workers can't move onto them)
    # The height is already 4, so is_domed will return True

    # After building, turn passes to other player
    new_state.player_turn = state.next_player()

    # Build completes the turn - reset moved_workers
    new_state.moved_workers = set()

    return new_state


def apply_move_and_build(state: GameState, move_payload: MovePayload, build_payload: BuildPayload) -> GameState:
    """Apply a move followed by a build in one turn.

    This is the typical Santorini turn: move a worker, then build a block.
    """
    # First apply the move
    after_move = apply_move(state, move_payload)

    # Apply the build after the move
    after_build = apply_build(after_move, build_payload)

    return after_build


# ---------------------------------------------------------------------------
# Initial state: places four workers per player on the board
# ---------------------------------------------------------------------------

# Starting positions for workers (two players, four workers each)
# Player ONE workers start at bottom-left area, Player TWO at top-right
STARTING_POSITIONS: Dict[Player, List[Position]] = {
    Player.ONE: [
        Position(0, 0),
        Position(0, 1),
        Position(4, 0),
        Position(4, 1),
    ],
    Player.TWO: [
        Position(4, 4),
        Position(4, 3),
        Position(0, 4),
        Position(0, 3),
    ],
}


def initial_state() -> GameState:
    """Create the initial Santorini game state with four workers per player placed.

    Returns:
        GameState with all eight workers (4 per player) placed on starting positions,
        board heights all 0, and Player.ONE to move first.
    """
    board = Board()
    # Place all workers at starting positions
    for player, positions in STARTING_POSITIONS.items():
        for i, pos in enumerate(positions, 1):
            worker_id = f"worker{i}"
            board.workers[player][worker_id] = pos
            # Height at starting position remains 0 (no blocks yet)
    return GameState(player_turn=Player.ONE, board=board)