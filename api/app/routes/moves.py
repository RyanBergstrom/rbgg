"""Move flow routes — generic dispatch via GameEngine and validator registry."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Path

from app.core.game_store import get_state, set_state, push_undo, pop_undo, clear_state, clear_undo
from app.core.log import trace, trace_move
from app.games.registry import ensure_validator
from app.core.repository import (
    create_session,
    get_session,
    load_game_state,
    save_game_state,
    complete_session,
)

router = APIRouter(prefix="/api/v1/moves", tags=["moves"])
BOT_NAMES = ("Stacy", "Trey", "Bella", "Stitch")


def _count_round_summaries(state) -> int:
    game_data = getattr(state, "game_data", {})
    summaries = game_data.get("round_summaries", []) if isinstance(game_data, dict) else []
    return len(summaries) if isinstance(summaries, list) else 0


def _trace_lost_cities_scoring(game_id: str, screen_state: dict, previous_round_count: int) -> None:
    if game_id != "lost_cities":
        return
    game_data = screen_state.get("game_data", {})
    round_summaries = game_data.get("round_summaries", [])
    if isinstance(round_summaries, list):
        for summary in round_summaries[previous_round_count:]:
            trace("routes", "lost_cities_round_summary", game_id=game_id, summary=summary)
    if screen_state.get("winner"):
        trace(
            "routes",
            "lost_cities_final_summary",
            game_id=game_id,
            winner=screen_state.get("winner"),
            scores=game_data.get("scores"),
            score_breakdown=game_data.get("score_breakdown"),
            round_summaries=round_summaries,
        )


def _get_session_state(session_id: int):
    """Load a session from SQLite and cache it by session ID."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    state = get_state(session_id)
    if state is None:
        state = load_game_state(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} has no saved state")
        set_state(session_id, state)

    return session, state


def _persist_state(session_id: int, state=None) -> None:
    """Save the full GameState object to the DB if a session exists."""
    import json
    if state is None:
        state = get_state(session_id)
    if state is not None:
        state_json = json.dumps(state.model_dump(mode="json"))
        if not save_game_state(session_id, state_json):
            raise HTTPException(status_code=409, detail="Session state was modified by another request")


def _build_session_result_summary(state, result: dict) -> dict:
    """Build a compact searchable result summary from the terminal state."""
    game_data = getattr(state, "game_data", {}) if state is not None else {}
    winner = result.get("winner") or getattr(state, "winner", None)
    return {
        "game_type": getattr(state, "game_type", None),
        "winner": winner,
        "difficulty": getattr(state, "difficulty", None),
        "version": getattr(state, "version", 0),
        "turn_number": getattr(state, "turn_number", 0),
        "round": game_data.get("round") if isinstance(game_data, dict) else None,
        "scores": game_data.get("scores") if isinstance(game_data, dict) else None,
        "last_round_summary": game_data.get("last_round_summary") if isinstance(game_data, dict) else None,
        "round_summaries": game_data.get("round_summaries") if isinstance(game_data, dict) else None,
        "players": [
            {
                "player_id": player.player_id,
                "name": player.name,
                "color": player.color,
            }
            for player in getattr(state, "players", [])
        ],
    }


def _complete_session_if_finished(session_id: int, state, result: dict) -> None:
    """Persist completion and statistics when a terminal transition occurs."""
    if result.get("winner") or state.winner:
        game_data = getattr(state, "game_data", {})
        complete_session(
            session_id,
            total_moves=state.version,
            total_turns=state.turn_number,
            winner=result.get("winner") or state.winner,
            final_scores=game_data.get("scores") if isinstance(game_data, dict) else None,
            result_summary=_build_session_result_summary(state, result),
        )


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
    import inspect
    import secrets

    requested_player_count = body.get("playerCount")
    if game_id == "bus":
        requested_player_count = requested_player_count or body.get("minPlayers", 3)
        try:
            requested_player_count = int(requested_player_count)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="playerCount must be an integer")
        if requested_player_count < 3 or requested_player_count > 5:
            raise HTTPException(status_code=422, detail="Bus requires 3 to 5 players")
    else:
        requested_player_count = 2

    player_colors = ["#cc0000", "#3b8d3b", "#1d70b8", "#e0a800", "#333333"]
    players = [
        PlayerInfo(
            player_id=f"player_{index + 1}",
            name=(
                body.get("playerName", "Player One")
                if index == 0
                else BOT_NAMES[index - 1] if index - 1 < len(BOT_NAMES) else f"Bot {index}"
            ),
            score=0,
            color=player_colors[index],
        )
        for index in range(requested_player_count)
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

    rng_seed = body["rng_seed"] if "rng_seed" in body else secrets.randbits(64)
    initializer = validator.initial_game_data
    initializer_parameters = inspect.signature(initializer).parameters
    initializer_kwargs = {}
    if "rng_seed" in initializer_parameters:
        initializer_kwargs["rng_seed"] = rng_seed
    if "player_ids" in initializer_parameters:
        initializer_kwargs["player_ids"] = [player.player_id for player in players]
    if "scenario_id" in initializer_parameters:
        scenario_id = body.get("scenario_id") or body.get("scenarioId")
        if scenario_id:
            initializer_kwargs["scenario_id"] = scenario_id
    initial_game_data = initializer(**initializer_kwargs)
    rng_state_json = initial_game_data.pop("_rng_state_json", "{}")

    state = GameState(
        state_id=f"{game_id}-state",
        game_type=game_id,
        topology=Topology.grid,
        rng_seed=rng_seed,
        rng_state_json=rng_state_json,
        players=players,
        current_player_index=0,
        game_data=initial_game_data if hasattr(validator, 'initial_game_data') else {},
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

    session = create_session(profile_id="default-profile", game_id=game_id, state_id=game_id)
    state.state_id = f"{game_id}-session-{session['id']}"
    set_state(session["id"], state)
    _persist_state(session["id"], state)

    # Get engine and build screen state
    try:
        engine = _get_engine(game_id)
        initial_player = state.game_data.get("current_player")
        initial_moves = engine.get_legal_moves(state, initial_player) if initial_player else []
        screen_state = engine.build_screen_state(state, initial_moves)
    except Exception:
        screen_state = {}

    response = {
        "player": {"player_id": players[0].player_id, "name": players[0].name, "color": players[0].color},
        "turn": {"turn_id": state.turn.turn_id, "player_id": state.turn.player_id, "topology": state.turn.topology.value},
        "game_id": game_id,
        "session_id": session["id"],
        "screen_state": screen_state,
    }
    if game_id != "twilight_struggle":
        response["rng_seed"] = state.rng_seed
        response["rng_state_json"] = state.rng_state_json
    return response


@router.post("/legal-moves", response_model=dict)
def get_legal_moves(body: dict = Body(default={})) -> dict:
    """Return legal moves for the current player, with screen state."""
    session_id = body.get("session_id", body.get("sessionId"))
    if session_id is None:
        raise HTTPException(status_code=422, detail="session_id required")
    session, state = _get_session_state(int(session_id))
    game_id = session["game_id"]

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    # Prefer the game's own current_player (from game_data) over the engine index
    game_data = getattr(state, "game_data", {})
    player_id = game_data.get("current_player")
    if not player_id and state.players:
        player_id = state.players[state.current_player_index].player_id
    if player_id is None:
        return {"legal_moves": [], "screen_state": {}}

    moves_list = engine.get_legal_moves(state, player_id)
    screen_state = engine.build_screen_state(state, moves_list)
    game_data = getattr(state, "game_data", {})
    pending = game_data.get("_pending_event") if isinstance(game_data, dict) else None
    if isinstance(pending, dict) and pending.get("our_man_tehran"):
        moves_list = [{key: value for key, value in move.items() if key != "revealed_cards"} for move in moves_list]
        if game_data.get("faction_by_player", {}).get(player_id) != "us":
            screen_state["legal_moves"] = []
    return {"legal_moves": moves_list, "screen_state": screen_state}


@router.post("/debug-load/{session_id}", response_model=dict)
def debug_load_state(session_id: int = Path(...), body: dict = Body(...)) -> dict:
    """Overwrite the in-memory game_data with debug-pasted state.

    Accepts a body with optional ``game_data`` and/or ``current_player_index``
    fields.  Merges them into the existing GameState so the backend uses the
    same board the frontend is displaying.
    """
    _, state = _get_session_state(session_id)

    game_data = body.get("game_data")
    if game_data is not None:
        state.game_data = game_data

    current_player_index = body.get("current_player_index")
    if current_player_index is not None:
        state.current_player_index = current_player_index

    winner = body.get("winner")
    if winner is not None:
        state.winner = winner

    set_state(session_id, state)
    _persist_state(session_id, state)
    return {"status": "ok"}


@router.post("/confirm/{session_id}", response_model=dict)
def confirm_turn(session_id: int = Path(...)) -> dict:
    """Handle confirm action — advance past confirm phase to next player."""
    session, state = _get_session_state(session_id)
    game_id = session["game_id"]

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    result = engine.confirm_turn(state)
    set_state(session_id, state)
    _persist_state(session_id, state)
    _complete_session_if_finished(session_id, state, result)

    # Build screen state with legal moves for next player
    game_data_after = getattr(state, "game_data", {})
    player_id = game_data_after.get("current_player")
    if not player_id and state.players:
        player_id = state.players[state.current_player_index].player_id
    legal_moves = engine.get_legal_moves(state, player_id) if player_id else []
    screen_state = engine.build_screen_state(state, legal_moves)

    return {**result, "screen_state": screen_state}


@router.post("/undo/{session_id}", response_model=dict)
def undo_move(session_id: int = Path(...)) -> dict:
    """Undo the last human move by restoring the previous state snapshot."""
    _, current_state = _get_session_state(session_id)
    snapshot = pop_undo(session_id)
    if snapshot is None:
        raise HTTPException(status_code=400, detail="Nothing to undo")

    # Reconstruct GameState from snapshot
    from app.core.game_state import GameState
    restored_state = GameState(**snapshot)

    set_state(session_id, restored_state)
    _persist_state(session_id, restored_state)

    # Build screen state with legal moves
    try:
        engine = _get_engine(current_state.game_type)
    except RuntimeError:
        raise HTTPException(
            status_code=501,
            detail=f"Validator not registered for {current_state.game_type}",
        )

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
    session_id = body.get("sessionId", body.get("session_id"))
    if session_id is None:
        raise HTTPException(status_code=422, detail="sessionId required")
    session_id = int(session_id)
    session, state = _get_session_state(session_id)
    game_id = session["game_id"]
    import os
    default_provider = os.environ.get("RBGG_LOST_CITIES_AI_PROVIDER", "ppo") if game_id == "lost_cities" else "mcts"
    if game_id == "bus":
        default_provider = os.environ.get("RBGG_BUS_AI_PROVIDER", "mcts")
    provider = body.get("provider", default_provider)
    if not isinstance(provider, str) or provider not in {"mcts", "ppo"}:
        raise HTTPException(status_code=422, detail="provider must be 'mcts' or 'ppo'")
    if provider == "ppo" and game_id not in {"lost_cities", "bus"}:
        raise HTTPException(status_code=422, detail="PPO provider is currently supported only for Lost Cities and Bus")
    ai_difficulty = body.get("aiDifficulty", body.get("ai_difficulty", "hard"))
    if provider == "ppo" and (
        not isinstance(ai_difficulty, str)
        or ai_difficulty not in {"easy", "medium", "hard"}
    ):
        raise HTTPException(status_code=422, detail="aiDifficulty must be 'easy', 'medium', or 'hard'")

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

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

    last_ai_provider = "mcts"

    def _choose_ai_move(st, pid):
        """Run MCTS or heuristic to choose a move for the given player."""
        nonlocal last_ai_provider
        moves = engine.get_legal_moves(st, pid)
        if not moves:
            return None
        if provider == "ppo":
            try:
                if game_id == "lost_cities":
                    from app.games.lost_cities.rl_inference import choose_live_move

                    chosen = choose_live_move(
                        engine._build_state_dict(st),
                        pid,
                        engine.validator,
                        difficulty=ai_difficulty,
                    )
                elif game_id == "bus":
                    from app.games.bus.rl_inference import choose_live_move

                    chosen = choose_live_move(
                        engine._build_state_dict(st),
                        pid,
                        engine.validator,
                        difficulty=ai_difficulty,
                    )
                else:
                    raise ValueError(f"PPO provider not supported for {game_id}")
                if chosen not in moves:
                    raise ValueError("PPO returned a move outside the engine's live legal moves")
                last_ai_provider = "ppo"
                return chosen
            except Exception as exc:
                trace("routes", "ppo_fallback", game_id=game_id, player_id=pid, error=repr(exc))
                # Optional RL dependencies, model files, and inference failures
                # must never prevent the existing MCTS policy from making a move.
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
                        full_game_rollout=cfg.full_game_rollout,
                        strategy=cfg.strategy,
                        hot_pool_size=cfg.hot_pool_size,
                        admission_interval=cfg.admission_interval,
                        final_budget_fraction=cfg.final_budget_fraction,
                        confidence_constant=cfg.confidence_constant,
                        discard_ceiling=cfg.discard_ceiling,
                        diagnostic_enabled=cfg.diagnostic_enabled,
                        diagnostic_max_records=cfg.diagnostic_max_records,
                        diagnostic_extremes_per_root=cfg.diagnostic_extremes_per_root,
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
            last_ai_provider = "mcts"
            return mcts.search(state_dict, pid).move
        else:
            last_ai_provider = "heuristic"
            return engine.validator.recommend_ai_move(
                engine._build_state_dict(st), moves
            )

    previous_round_count = _count_round_summaries(state)
    chosen_move = _choose_ai_move(state, player_id)
    if chosen_move is None:
        return {"status": "no_legal_moves", "move": None}

    try:
        result = engine.submit_move(state, chosen_move)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "VERSION_CONFLICT", "message": str(exc)},
        ) from exc
    set_state(session_id, state)
    _persist_state(session_id, state)
    _complete_session_if_finished(session_id, state, result)

    # Continue making AI moves until the turn passes to another player
    # (handles phase-based games like Lost Cities, multi-jump continuations,
    # and consecutive bot seats in setup/selection phases)
    game_data_loop = getattr(state, "game_data", {})
    current_player_loop = game_data_loop.get("current_player")
    human_player_id = state.players[0].player_id if state.players else None
    while current_player_loop and current_player_loop != human_player_id and not result.get("winner"):
        chosen_move = _choose_ai_move(state, current_player_loop)
        if chosen_move is None:
            break
        try:
            result = engine.submit_move(state, chosen_move)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "VERSION_CONFLICT", "message": str(exc)},
            ) from exc
        set_state(session_id, state)
        _persist_state(session_id, state)
        game_data_loop = getattr(state, "game_data", {})
        current_player_loop = game_data_loop.get("current_player")

    # Always confirm the AI turn to advance past confirm_required phases
    engine.confirm_turn(state)
    set_state(session_id, state)
    _persist_state(session_id, state)
    _complete_session_if_finished(session_id, state, result)

    # Build screen state with legal moves for next player
    game_data_final = getattr(state, "game_data", {})
    response_provider = last_ai_provider
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
    _trace_lost_cities_scoring(game_id, screen_state, previous_round_count)

    return {
        "status": "ok",
        "move": chosen_move,
        "ai_provider": response_provider,
        "ai_difficulty": ai_difficulty if provider == "ppo" else None,
        "winner": result.get("winner"),
        "player_turn": state.players[state.current_player_index].player_id if state.players else None,
        "screen_state": screen_state,
    }


@router.post("/{session_id}/move", response_model=dict)
def submit_move(session_id: int, move: dict = Body(...)) -> dict:
    """Submit a player move through the GameEngine."""
    session, state = _get_session_state(session_id)
    game_id = session["game_id"]

    try:
        engine = _get_engine(game_id)
    except RuntimeError:
        raise HTTPException(status_code=501, detail=f"Validator not registered for {game_id}")

    player_id = state.players[state.current_player_index].player_id if state.players else None
    if player_id is None:
        raise HTTPException(status_code=422, detail="No current player")

    # Save state snapshot for undo (before applying the move)
    push_undo(session_id, state)
    previous_round_count = _count_round_summaries(state)

    try:
        result = engine.submit_move(state, move, expected_version=state.version)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "VERSION_CONFLICT", "message": str(exc)},
        ) from exc
    set_state(session_id, state)
    _persist_state(session_id, state)
    _complete_session_if_finished(session_id, state, result)

    if game_id == "twilight_struggle":
        trace("routes", "player_move", game_id=game_id, player_id=move.get("player_id"), move_type=move.get("type"))
    else:
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
    _trace_lost_cities_scoring(game_id, screen_state, previous_round_count)

    return {
        "status": result.get("status", "ok"),
        "board": screen_state.get("game_data", {}) if game_id == "twilight_struggle" else state.game_data,
        "winner": result.get("winner"),
        "player_turn": state.players[state.current_player_index].player_id if state.players else None,
        "version": state.version,
        "screen_state": screen_state,
    }
