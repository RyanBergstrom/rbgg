from fastapi import APIRouter, Depends, HTTPException

from app.games.registry import ensure_validator
from app.core.game_store import set_state, clear_state, clear_undo
from app.core.repository import create_session, list_sessions, delete_session, load_game_state, save_game_state

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _get_profile_id() -> str:
    """Dependency that provides the current viewer's profile ID."""
    return "default-profile"


@router.get("/", response_model=list[dict])
def list_sessions_endpoint(profile_id: str = Depends(_get_profile_id)) -> list[dict]:
    """Return all sessions for the current profile."""
    return list_sessions(profile_id=profile_id)


@router.get("/filter", response_model=list[dict])
def list_sessions_filtered(
    game_id: str | None = None,
    profile_id: str = Depends(_get_profile_id),
) -> list[dict]:
    """Return sessions filtered by optional game_id."""
    return list_sessions(profile_id=profile_id, game_id=game_id)


@router.delete("/{session_id}", response_model=dict)
def delete_session_endpoint(session_id: int) -> dict:
    """Delete a session by its ID."""
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    clear_state(session_id)
    clear_undo(session_id)
    return {"deleted": True, "session_id": session_id}


@router.post("/{session_id}/load", response_model=dict)
def load_session(session_id: int) -> dict:
    """Load a saved session's full GameState into memory and return screen state."""
    state = load_game_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} has no saved state")

    game_id = state.game_type
    set_state(session_id, state)

    try:
        from app.games.registry import ensure_validator
        from app.core.engine import GameEngine
        validator = ensure_validator(game_id)
        engine = GameEngine(game_id, validator)
        game_data = getattr(state, "game_data", {})
        player_id = game_data.get("current_player")
        if not player_id and state.players:
            player_id = state.players[state.current_player_index].player_id
        legal_moves = engine.get_legal_moves(state, player_id) if player_id else []
        screen_state = engine.build_screen_state(state, legal_moves)
    except Exception:
        screen_state = {}

    from app.games.catalog import get_game
    game = get_game(game_id)

    return {
        "id": game["id"] if game else game_id,
        "name": game["name"] if game else game_id,
        "type": game["type"] if game else "unknown",
        "cover_image": game.get("cover_image") if game else None,
        "difficulty": game.get("difficulty") if game else None,
        "state": {
            "player_turn": state.players[state.current_player_index].player_id if state.players else None,
            "winner": state.winner,
            "game_data": (
                screen_state.get("game_data", {})
                if game_id == "twilight_struggle"
                else state.game_data
            ),
        },
        "turn": state.turn.__dict__ if state.turn else None,
        "screen_state": screen_state,
        "session_id": session_id,
    }
