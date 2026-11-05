from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.games import router as games_router
from app.routes.moves import router as moves_router
from app.routes.sessions import router as sessions_router
from app.routes.settings import router as settings_router
from app.routes.asset_review import router as asset_review_router

app = FastAPI(title="rbgg API", version="0.1.0")

from app.core.legal_move_interface import IllegalMoveError


@app.exception_handler(IllegalMoveError)
async def illegal_move_handler(request, exc: IllegalMoveError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "ILLEGAL_MOVE", "message": str(exc)}},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://rbgg-web.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)
app.include_router(moves_router)
app.include_router(sessions_router)
app.include_router(settings_router)
app.include_router(asset_review_router)

# Serve game cover images
_img_dir = Path(__file__).resolve().parent.parent / "img"
_bus_img_dir = Path(__file__).resolve().parent / "games" / "bus"
_twilight_img_dir = Path(__file__).resolve().parents[2] / "documentation" / "twilight-struggle" / "images"
if _bus_img_dir.is_dir():
    app.mount(
        "/api/v1/img/bus",
        StaticFiles(directory=str(_bus_img_dir)),
        name="bus-game-images",
    )
if _twilight_img_dir.is_dir():
    app.mount(
        "/api/v1/img/twilight-struggle",
        StaticFiles(directory=str(_twilight_img_dir)),
        name="twilight-struggle-images",
    )
_fof_img_dir = Path(__file__).resolve().parent.parent / "img" / "fof"
if _fof_img_dir.is_dir():
    app.mount(
        "/api/v1/img/fof",
        StaticFiles(directory=str(_fof_img_dir)),
        name="fof-game-images",
    )
if _img_dir.is_dir():
    app.mount(
        "/api/v1/img",
        StaticFiles(directory=str(_img_dir)),
        name="game-images",
    )

# Register checkers game
from app.games.catalog import register_game
from app.games.registry import register_validator
from app.games.checkers.validator import CheckersValidator
from app.games.bus.validator import BusValidator
from app.games.lost_cities.validator import LostCitiesValidator
from app.games.twilight_struggle.validator import TwilightStruggleValidator
from app.games.fields_of_fire.validator import FieldsOfFireValidator
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

# Register Bus game
_bus_config = load_game_config("bus")
_bus_cover = _bus_config.cover_image
if _bus_cover and _bus_cover.startswith("api/img/"):
    _bus_cover = _bus_cover[len("api/img/"):]
register_game(
    "bus",
    "Bus",
    "bus",
    min_players=_bus_config.min_players,
    max_players=_bus_config.max_players,
    cover_image=_bus_cover,
)
register_validator("bus", BusValidator())

# Twilight Struggle is exposed for the in-progress human UI. Rules/card sign-off
# remains open; do not treat catalog presence as a complete-game readiness claim.
register_game(
    "twilight_struggle",
    "Twilight Struggle",
    "twilight_struggle",
    min_players=2,
    max_players=2,
    cover_image="twilight-struggle/cover.jpg",
)
register_validator("twilight_struggle", TwilightStruggleValidator())

# Register Fields of Fire (Deluxe) — scaffold; rules implementation in progress.
_fof_config = load_game_config("fields_of_fire")
register_game(
    "fields_of_fire",
    "Fields of Fire (Deluxe)",
    "fields_of_fire",
    min_players=_fof_config.min_players,
    max_players=_fof_config.max_players,
    cover_image="fof/cover.png",
)
register_validator("fields_of_fire", FieldsOfFireValidator())
