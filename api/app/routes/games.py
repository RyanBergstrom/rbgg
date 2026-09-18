from fastapi import APIRouter, HTTPException, Path

from app.games.catalog import list_games, get_game
from app.core.game_store import get_state

router = APIRouter(prefix="/api/v1/games", tags=["games"])


@router.get("/", response_model=list[dict])
def list_games_endpoint() -> list[dict]:
    """Return all available games."""
    return list_games()


@router.get("/{game_id}", response_model=dict)
def get_game_by_id(game_id: str = Path(...)) -> dict:
    """Return game detail including current state if a game is in progress."""
    game = get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    state = get_state(game_id)
    if state is not None:
        from app.core.game_state import GameState as CoreGameState
        if isinstance(state, CoreGameState):
            # Build screen state if possible
            screen_state = {}
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
                pass

            return {
                "id": game["id"],
                "name": game["name"],
                "type": game["type"],
                "cover_image": game.get("cover_image"),
                "difficulty": game.get("difficulty"),
                "state": {
                    "player_turn": state.players[state.current_player_index].player_id if state.players else None,
                    "winner": state.winner,
                    "game_data": state.game_data,
                },
                "turn": state.turn.__dict__ if state.turn else None,
                "screen_state": screen_state,
            }

    return {
        "id": game["id"],
        "name": game["name"],
        "type": game["type"],
        "cover_image": game.get("cover_image"),
        "difficulty": game.get("difficulty"),
        "min_players": game["min_players"],
        "max_players": game["max_players"],
        "state": None,
        "turn": None,
    }
