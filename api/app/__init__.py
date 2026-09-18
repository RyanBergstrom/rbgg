from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.games import router as games_router
from app.routes.moves import router as moves_router
from app.routes.sessions import router as sessions_router
from app.routes.settings import router as settings_router

app = FastAPI(title="rbgg API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)
app.include_router(moves_router)
app.include_router(sessions_router)
app.include_router(settings_router)

# Serve game cover images
_img_dir = Path(__file__).resolve().parent.parent / "img"
if _img_dir.is_dir():
    app.mount("/api/v1/img", StaticFiles(directory=str(_img_dir)), name="game-images")

# Register checkers game
from app.games.catalog import register_game
from app.games.registry import register_validator
from app.games.checkers.validator import CheckersValidator
from app.games.lost_cities.validator import LostCitiesValidator
from app.core.config_loader import load_game_config

_checkers_config = load_game_config("checkers")
_cover_image = _checkers_config.cover_image
if _cover_image and _cover_image.startswith("api/img/"):
    _cover_image = _cover_image[len("api/img/"):]
register_game(
    "checkers",
    "Checkers",
    "checkers",
    min_players=_checkers_config.min_players,
    max_players=_checkers_config.max_players,
    cover_image=_cover_image,
    difficulty=_checkers_config.difficulty.to_dict() if _checkers_config.difficulty else None,
)
register_validator("checkers", CheckersValidator())

# Register Lost Cities game
_lost_cities_config = load_game_config("lost_cities")
_lc_cover = _lost_cities_config.cover_image
if _lc_cover and _lc_cover.startswith("api/img/"):
    _lc_cover = _lc_cover[len("api/img/"):]
register_game(
    "lost_cities",
    "Lost Cities",
    "lost_cities",
    min_players=_lost_cities_config.min_players,
    max_players=_lost_cities_config.max_players,
    cover_image=_lc_cover,
    difficulty=_lost_cities_config.difficulty.to_dict() if _lost_cities_config.difficulty else None,
)
register_validator("lost_cities", LostCitiesValidator())
