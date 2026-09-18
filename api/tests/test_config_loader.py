"""Tests for YAML config loader and fail-fast behavior."""

from app.core.config_loader import ConfigLoadError, load_config, load_all_configs, load_game_config, clear_config_cache
from app.core.config_schema import (
    GameConfig, PanelConfig, ComponentConfig, GridConfig,
    RoundConfig, TurnConfig, PhaseConfig, ConfirmConfig,
)
import tempfile
import os


def _make_temp_config(stem: str, content: str) -> str:
    """Create a temporary config file and return its path."""
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, f"{stem}.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_load_valid_config_returns_dict():
    path = _make_temp_config("valid", "players:\n  - Alice\n  - Bob\n")
    try:
        data = load_config(path)
        assert isinstance(data, dict)
        assert "players" in data
    finally:
        os.unlink(path)


def test_load_config_invalid_raises_config_load_error():
    try:
        load_config("nonexistent_file.yaml")
        assert False
    except ConfigLoadError:
        pass

    path = _make_temp_config("invalid", "key: [unclosed list\n")
    try:
        load_config(path)
        assert False
    except ConfigLoadError:
        pass
    finally:
        os.unlink(path)


def test_load_all_configs_keys_by_game_id():
    path1 = _make_temp_config("game1", "game_id: game1\n")
    path2 = _make_temp_config("game2", "game_id: game2\n")
    try:
        configs, errors = load_all_configs(path1, path2)
        assert isinstance(configs, dict)
        assert len(configs) == 2
        assert "game1" in configs
        assert "game2" in configs
        assert errors == []
    finally:
        for p in [path1, path2]:
            if os.path.exists(p):
                os.unlink(p)


def test_load_all_configs_raises_on_first_malformed_file():
    valid_path = _make_temp_config("valid", "valid: true\n")
    invalid_path = _make_temp_config("invalid", "key: [unclosed list\n")
    try:
        configs, errors = load_all_configs(valid_path, invalid_path)
        assert "valid" in configs
        assert "invalid" not in configs
        assert len(errors) == 1
        assert errors[0] is not None
        assert len(errors[0]) > 0
    finally:
        for p in [valid_path, invalid_path]:
            if os.path.exists(p):
                os.unlink(p)


def test_load_game_config_parses_checkers():
    """Verify that load_game_config parses checkers with rounds/turns/phases."""
    clear_config_cache()
    config = load_game_config("checkers")
    assert isinstance(config, GameConfig)

    # Required panels
    assert "game_progress" in config.panels
    assert "main_board" in config.panels

    # Board components
    main_board = config.panels["main_board"]
    assert "board" in main_board.components
    assert "red_pieces" in main_board.components
    assert "black_pieces" in main_board.components

    board = main_board.components["board"]
    assert board.name == "Board"
    assert board.shape == "rectangle"
    assert isinstance(board.grid, GridConfig)
    assert board.grid.rows == 8
    assert board.grid.columns == 8

    red = main_board.components["red_pieces"]
    assert red.stackable is True
    assert red.stack_name == "red_pool"

    # Rounds/turns/phases
    assert len(config.rounds) == 1
    rnd = config.rounds[0]
    assert rnd.name == "Main Game"
    assert len(rnd.turns) == 1

    turn = rnd.turns[0]
    assert turn.name == "Player Turn"
    assert len(turn.phases) == 2

    phase1 = turn.phases[0]
    assert phase1.name == "Player_Turn"
    assert phase1.text == "Make your move"
    assert phase1.order == 1
    assert phase1.confirm is not None
    assert phase1.confirm.required is False

    phase2 = turn.phases[1]
    assert phase2.name == "Pass_Turn"
    assert phase2.text == "Confirm your move"
    assert phase2.order == 2
    assert phase2.confirm is not None
    assert phase2.confirm.required is True
    assert phase2.confirm.name == "Confirm"
    assert phase2.confirm.description == "End your turn"


def test_load_game_config_caches():
    clear_config_cache()
    config1 = load_game_config("checkers")
    config2 = load_game_config("checkers")
    assert config1 is config2


def test_load_game_config_missing_file():
    clear_config_cache()
    try:
        load_game_config("nonexistent_game_xyz")
        assert False
    except ConfigLoadError:
        pass
