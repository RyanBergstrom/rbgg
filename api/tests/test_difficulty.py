"""Tests for difficulty system — config parsing, state persistence, AI integration."""

import pytest

from app.core.config_schema import DifficultyConfig, GameConfig, PanelConfig
from app.core.config_loader import load_game_config, clear_config_cache
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology


# ── DifficultyConfig tests ──────────────────────────────────────────

class TestDifficultyConfig:
    def test_to_dict_includes_levels_and_default(self):
        dc = DifficultyConfig(levels={"easy": 50, "hard": 500}, default="easy")
        d = dc.to_dict()
        assert d["easy"] == 50
        assert d["hard"] == 500
        assert d["default"] == "easy"

    def test_empty_levels(self):
        dc = DifficultyConfig(levels={}, default="")
        d = dc.to_dict()
        assert d == {"default": ""}


# ── Config loader tests ─────────────────────────────────────────────

class TestConfigLoaderDifficulty:
    def test_checkers_config_has_difficulty(self):
        clear_config_cache()
        config = load_game_config("checkers")
        assert config.difficulty is not None
        assert isinstance(config.difficulty, DifficultyConfig)
        assert config.difficulty.levels["easy"] == 50
        assert config.difficulty.levels["medium"] == 300
        assert config.difficulty.levels["hard"] == 1500
        assert config.difficulty.levels["expert"] == 5000
        assert config.difficulty.default == "medium"

    def test_config_to_dict_includes_difficulty(self):
        clear_config_cache()
        config = load_game_config("checkers")
        d = config.to_dict()
        assert "difficulty" in d
        assert d["difficulty"]["easy"] == 50
        assert d["difficulty"]["default"] == "medium"


# ── GameState tests ─────────────────────────────────────────────────

class TestGameStateDifficulty:
    def test_difficulty_defaults_to_none(self):
        state = GameState(
            state_id="test",
            turn=TurnInfo(turn_id="t1", player_id="p1", topology=Topology.grid),
        )
        assert state.difficulty is None

    def test_difficulty_can_be_set(self):
        state = GameState(
            state_id="test",
            turn=TurnInfo(turn_id="t1", player_id="p1", topology=Topology.grid),
            difficulty="hard",
        )
        assert state.difficulty == "hard"

    def test_to_player_view_preserves_difficulty(self):
        state = GameState(
            state_id="test",
            turn=TurnInfo(turn_id="t1", player_id="p1", topology=Topology.grid),
            difficulty="expert",
            players=[PlayerInfo(player_id="p1", name="Test")],
        )
        from app.core.game_state import to_player_view
        view = to_player_view(state, "p1")
        assert view.difficulty == "expert"


# ── Catalog tests ───────────────────────────────────────────────────

class TestCatalogDifficulty:
    def test_register_game_with_difficulty(self):
        from app.games.catalog import register_game, get_game, GAME_CATALOG
        # Save and restore
        saved = GAME_CATALOG.get("test_diff_game")
        try:
            register_game(
                "test_diff_game", "Test Game", "test",
                difficulty={"easy": 10, "hard": 100, "default": "easy"},
            )
            game = get_game("test_diff_game")
            assert game["difficulty"]["easy"] == 10
            assert game["difficulty"]["hard"] == 100
            assert game["difficulty"]["default"] == "easy"
        finally:
            if saved is not None:
                GAME_CATALOG["test_diff_game"] = saved
            else:
                GAME_CATALOG.pop("test_diff_game", None)

    def test_register_game_without_difficulty(self):
        from app.games.catalog import register_game, get_game, GAME_CATALOG
        saved = GAME_CATALOG.get("test_nodiff_game")
        try:
            register_game("test_nodiff_game", "Test Game", "test")
            game = get_game("test_nodiff_game")
            assert game["difficulty"] is None
        finally:
            if saved is not None:
                GAME_CATALOG["test_nodiff_game"] = saved
            else:
                GAME_CATALOG.pop("test_nodiff_game", None)
