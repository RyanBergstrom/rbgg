"""Move flow routes — generic dispatch via GameEngine and validator registry."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Path

from app.core.game_store import get_state, get_entry, set_state, push_undo, pop_undo
from app.core.log import trace, trace_move
from app.games.registry import ensure_validator
from app.core.repository import create_session, save_game_state

router = APIRouter(prefix="/api/v1/moves", tags=["moves"])


def _persist_state(game_id: str) -> None:
    """Save the full GameState object to the DB if a session exists."""
    import json
    entry = get_entry(game_id)
    if entry is not None and entry.session_id is not None:
        state = entry.state
        state_json = json.dumps(state.model_dump(mode="json"))
        save_game_state(entry.session_id, state_json)


def _get_engine(game_id: str):
    """Get a GameEngine for the given game_id."""
    from app.core.engine import GameEngine
    validator = ensure_validator(game_id)
    return GameEngine(game_id, validator)


@router.post("/start-session/{game_id}", response_model=dict)
def start_session(game_id: str = Path(...), body: dict = Body(default={})) -> dict:
    """Create a new session for *game_id* and return initial state with phase info."""
    from app.games.catalog import get_game
    game = get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    try:
        validator = ensure_validator(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology
    from app.core.config_loader import load_game_config
    import random

    players = [
        PlayerInfo(player_id="player_1", name=body.get("playerName", "Player One"), score=0, color=body.get("color", "#FFFFFF")),
        PlayerInfo(player_id="player_2", name="Player Two", score=0, color="#333333"),
    ]

    # Resolve difficulty from request body
    difficulty = None
    try:
        game_config = load_game_config(game_id)
        if game_config.difficulty:
            raw_diff = body.get("difficulty")
            if raw_diff and raw_diff != "default":
                if raw_diff in game_config.difficulty.levels:
                    difficulty = raw_diff
                else:
                    difficulty = game_config.difficulty.default
            else:
                difficulty = game_config.difficulty.default
    except Exception:
        pass

    state = GameState(
        state_id=f"{game_id}-state",
        game_type=game_id,
        topology=Topology.grid,
        rng_seed=body.get("rng_seed", random.randint(0, 2**32)),
        players=players,
        current_player_index=0,
        game_data=validator.initial_game_data() if hasattr(validator, 'initial_game_data') else {},
        difficulty=difficulty,
        turn=TurnInfo(
            turn_id="t1",
            player_id=players[0].player_id,
            topology=Topology.grid,
        ),
        current_round_index=0,
        current_turn_index=0,
        current_phase_index=0,
    )

    set_state(game_id, state)

    session = create_session(profile_id="default-profile", game_id=game_id, state_id=game_id)
    set_state(game_id, state, session_id=session["id"])
    _persist_state(game_id)

    # Get engine and build screen state
    try:
        engine = _get_engine(game_id)
        screen_state = engine.build_screen_state(state, [])
    except Exception:
        screen_state = {}

    return {
        "rng_seed": state.rng_seed,
        "rng_state_json": state.rng_state_json,
        "player": {"player_id": players[0].player_id, "name": players[0].name, "color": players[0].color},
        "turn": {"turn_id": state.turn.turn_id, "player_id": state.turn.player_id, "topology": state.turn.topology.value},
        "game_id": game_id,
        "session_id": session["id"],
        "screen_state": screen_state,
    }


@router.post("/legal-moves", response_model=dict)
def get_legal_moves(body: dict = Body(default={})) -> dict:
    """Return legal moves for the current player, with screen state."""
    game_id = body.get("game_id", "")
    state = get_state(game_id)
    if state is None:
        return {"legal_moves": [], "screen_state": {}}

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        return {"legal_moves": [], "screen_state": {}}

    # Prefer the game's own current_player (from game_data) over the engine index
    game_data = getattr(state, "game_data", {})
    player_id = game_data.get("current_player")
    if not player_id and state.players:
        player_id = state.players[state.current_player_index].player_id
    if player_id is None:
        return {"legal_moves": [], "screen_state": {}}

    moves_list = engine.get_legal_moves(state, player_id)
    screen_state = engine.build_screen_state(state, moves_list)

    return {"legal_moves": moves_list, "screen_state": screen_state}


@router.post("/debug-load/{game_id}", response_model=dict)
def debug_load_state(game_id: str = Path(...), body: dict = Body(...)) -> dict:
    """Overwrite the in-memory game_data with debug-pasted state.

    Accepts a body with optional ``game_data`` and/or ``current_player_index``
    fields.  Merges them into the existing GameState so the backend uses the
    same board the frontend is displaying.
    """
    state = get_state(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No active game")

    game_data = body.get("game_data")
    if game_data is not None:
        state.game_data = game_data

    current_player_index = body.get("current_player_index")
    if current_player_index is not None:
        state.current_player_index = current_player_index

    winner = body.get("winner")
    if winner is not None:
        state.winner = winner

    set_state(game_id, state)
    return {"status": "ok"}


@router.post("/confirm/{game_id}", response_model=dict)
def confirm_turn(game_id: str = Path(...)) -> dict:
    """Handle confirm action — advance past confirm phase to next player."""
    state = get_state(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No active game")

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    result = engine.confirm_turn(state)
    set_state(game_id, state)
    _persist_state(game_id)

    # Build screen state with legal moves for next player
    game_data_after = getattr(state, "game_data", {})
    player_id = game_data_after.get("current_player")
    if not player_id and state.players:
        player_id = state.players[state.current_player_index].player_id
    legal_moves = engine.get_legal_moves(state, player_id) if player_id else []
    screen_state = engine.build_screen_state(state, legal_moves)

    return {**result, "screen_state": screen_state}


@router.post("/undo/{game_id}", response_model=dict)
def undo_move(game_id: str = Path(...)) -> dict:
    """Undo the last human move by restoring the previous state snapshot."""
    snapshot = pop_undo(game_id)
    if snapshot is None:
        raise HTTPException(status_code=400, detail="Nothing to undo")

    # Reconstruct GameState from snapshot
    from app.core.game_state import GameState
    restored_state = GameState(**snapshot)

    set_state(game_id, restored_state)
    _persist_state(game_id)

    # Build screen state with legal moves
    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    game_data_after = getattr(restored_state, "game_data", {})
    player_id = game_data_after.get("current_player")
    if not player_id and restored_state.players:
        player_id = restored_state.players[restored_state.current_player_index].player_id
    legal_moves = engine.get_legal_moves(restored_state, player_id) if player_id else []
    screen_state = engine.build_screen_state(restored_state, legal_moves)

    return {
        "status": "undone",
        "screen_state": screen_state,
    }


@router.post("/ai", response_model=dict)
def post_ai_move(body: dict = Body(...)) -> dict:
    """Compute and apply an AI move for the current player."""
    game_id = body.get("gameId")
    if game_id is None:
        raise HTTPException(status_code=422, detail="gameId required")

    state = get_state(game_id)
    if state is None:
        return {"status": "no_legal_moves", "move": None}

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        return {"status": "no_legal_moves", "move": None}

    game_data = getattr(state, "game_data", {})
    player_id = game_data.get("current_player")
    if not player_id and state.players:
        player_id = state.players[state.current_player_index].player_id
    if player_id is None:
        return {"status": "no_legal_moves", "move": None}

    candidate_moves = engine.get_legal_moves(state, player_id)
    if not candidate_moves:
        return {"status": "no_legal_moves", "move": None}

    # Use MCTS if the validator provides an AI config
    from app.core.mcts import MCTSEngine, MCTSConfig
    from app.core.config_loader import load_game_config

    def _choose_ai_move(st, pid):
        """Run MCTS or heuristic to choose a move for the given player."""
        moves = engine.get_legal_moves(st, pid)
        if not moves:
            return None
        cfg = engine.validator.ai_config()
        if cfg is not None:
            try:
                game_config = load_game_config(game_id)
                if game_config.difficulty and st.difficulty:
                    cfg = MCTSConfig(
                        iterations=game_config.difficulty.levels.get(st.difficulty, cfg.iterations),
                        exploration_constant=cfg.exploration_constant,
                        max_depth=cfg.max_depth,
                        seed=cfg.seed,
                        workers=cfg.workers,
                    )
            except Exception:
                pass
            game_data_decide = getattr(st, "game_data", {})
            trace("routes", "ai_decide",
                  game_id=game_id,
                  player_id=pid,
                  phase=game_data_decide.get("current_phase"),
                  difficulty=getattr(st, "difficulty", None),
                  iterations=cfg.iterations,
                  workers=cfg.workers,
                  legal_move_count=len(moves),
                  legal_moves=moves)
            mcts = MCTSEngine(engine.validator, cfg)
            state_dict = engine._build_state_dict(st)
            return mcts.search(state_dict, pid).move
        else:
            return engine.validator.recommend_ai_move(
                engine._build_state_dict(st), moves
            )

    chosen_move = _choose_ai_move(state, player_id)
    if chosen_move is None:
        return {"status": "no_legal_moves", "move": None}

    result = engine.submit_move(state, chosen_move)
    set_state(game_id, state)
    _persist_state(game_id)

    # Continue making AI moves until the turn passes to another player
    # (handles phase-based games like Lost Cities and multi-jump continuations)
    game_data_loop = getattr(state, "game_data", {})
    current_player_loop = game_data_loop.get("current_player")
    while current_player_loop == player_id and not result.get("winner"):
        chosen_move = _choose_ai_move(state, current_player_loop)
        if chosen_move is None:
            break
        result = engine.submit_move(state, chosen_move)
        set_state(game_id, state)
        _persist_state(game_id)
        game_data_loop = getattr(state, "game_data", {})
        current_player_loop = game_data_loop.get("current_player")

    # Always confirm the AI turn to advance past confirm_required phases
    engine.confirm_turn(state)
    set_state(game_id, state)
    _persist_state(game_id)

    # Build screen state with legal moves for next player
    game_data_final = getattr(state, "game_data", {})
    next_player_id = game_data_final.get("current_player")
    if not next_player_id and state.players:
        next_player_id = state.players[state.current_player_index].player_id
    legal_moves = engine.get_legal_moves(state, next_player_id) if next_player_id else []
    screen_state = engine.build_screen_state(state, legal_moves)

    trace_move("routes", "ai_move", move=chosen_move, game_id=game_id)
    game_data_ss = screen_state.get("game_data", {})
    trace("routes", "screen_state",
          game_id=game_id,
          current_player=screen_state.get("current_player"),
          phase=screen_state.get("phase", {}).get("phase_name"),
          winner=screen_state.get("winner"),
          player_hands=game_data_ss.get("player_hands"),
          expeditions=game_data_ss.get("expeditions"),
          scores=game_data_ss.get("scores"),
          discard_piles={k: (v.get("cards", [])[-3:] if isinstance(v, dict) else v[-3:]) if v else [] for k, v in game_data_ss.get("discard_piles", {}).items()},
          draw_pile_count=game_data_ss.get("draw_pile", {}).get("count", 0) if isinstance(game_data_ss.get("draw_pile"), dict) else len(game_data_ss.get("draw_pile", [])),
          legal_moves=screen_state.get("legal_moves", []))

    return {
        "status": "ok",
        "move": chosen_move,
        "winner": result.get("winner"),
        "player_turn": state.players[state.current_player_index].player_id if state.players else None,
        "screen_state": screen_state,
    }


@router.post("/{game_id}/move", response_model=dict)
def submit_move(game_id: str, move: dict = Body(...)) -> dict:
    """Submit a player move through the GameEngine."""
    state = get_state(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No active game")

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    player_id = state.players[state.current_player_index].player_id if state.players else None
    if player_id is None:
        raise HTTPException(status_code=422, detail="No current player")

    # Save state snapshot for undo (before applying the move)
    push_undo(game_id, state)

    result = engine.submit_move(state, move, expected_version=state.version)
    set_state(game_id, state)
    _persist_state(game_id)

    trace_move("routes", "player_move", move=move, game_id=game_id)

    # Build screen state with legal moves for current player (may be same player for multi-jump)
    game_data_after = getattr(state, "game_data", {})
    next_player_id = game_data_after.get("current_player")
    if not next_player_id and state.players:
        next_player_id = state.players[state.current_player_index].player_id
    legal_moves = engine.get_legal_moves(state, next_player_id) if next_player_id else []
    screen_state = engine.build_screen_state(state, legal_moves)

    game_data_ss = screen_state.get("game_data", {})
    trace("routes", "screen_state",
          game_id=game_id,
          current_player=screen_state.get("current_player"),
          phase=screen_state.get("phase", {}).get("phase_name"),
          winner=screen_state.get("winner"),
          player_hands=game_data_ss.get("player_hands"),
          expeditions=game_data_ss.get("expeditions"),
          scores=game_data_ss.get("scores"),
          discard_piles={k: (v.get("cards", [])[-3:] if isinstance(v, dict) else v[-3:]) if v else [] for k, v in game_data_ss.get("discard_piles", {}).items()},
          draw_pile_count=game_data_ss.get("draw_pile", {}).get("count", 0) if isinstance(game_data_ss.get("draw_pile"), dict) else len(game_data_ss.get("draw_pile", [])),
          legal_moves=screen_state.get("legal_moves", []))

    return {
        "status": result.get("status", "ok"),
        "board": state.game_data,
        "winner": result.get("winner"),
        "player_turn": state.players[state.current_player_index].player_id if state.players else None,
        "version": state.version,
        "screen_state": screen_state,
    }
