"""Tests for game config schema and strict validators."""

from app.core.config_schema import (
    ComponentConfig,
    ConfirmConfig,
    GameConfig,
    GridConfig,
    PanelConfig,
    PhaseConfig,
    RoundConfig,
    TurnConfig,
)


# ── Component tests ────────────────────────────────────────────────────

def test_component_config_defaults():
    """Verify that ComponentConfig defaults are sensible."""
    comp = ComponentConfig(name="Test")
    assert comp.shape == "rectangle"
    assert comp.color is None
    assert comp.background_image is None
    assert comp.z_index == 0
    assert comp.grid is None
    assert comp.stackable is False
    assert comp.stack_name is None
    assert comp.rotate is None
    assert comp.clickable is True
    assert comp.hover_text is None


def test_component_invalid_shape_rejected():
    try:
        ComponentConfig(name="Bad", shape="triangle")
        assert False
    except ValueError as e:
        assert "shape" in str(e).lower()


def test_component_color_and_background_image_mutually_exclusive():
    try:
        ComponentConfig(name="Bad", color="#fff", background_image="/img.png")
        assert False
    except ValueError as e:
        assert "color" in str(e).lower() or "background_image" in str(e).lower()


def test_component_config_from_dict_with_grid():
    comp = ComponentConfig(**{
        "name": "Board",
        "shape": "rectangle",
        "grid": {"rows": 8, "columns": 8},
    })
    assert isinstance(comp.grid, GridConfig)
    assert comp.grid.rows == 8


def test_component_rotate_rejects_zero():
    try:
        ComponentConfig(name="Bad", rotate=0)
        assert False
    except ValueError:
        pass


def test_component_rotate_allows_positive():
    comp = ComponentConfig(name="Card", rotate=4)
    assert comp.rotate == 4


# ── Grid tests ─────────────────────────────────────────────────────────

def test_grid_config_validates_min_values():
    try:
        GridConfig(rows=0, columns=8)
        assert False
    except ValueError:
        pass

    try:
        GridConfig(rows=8, columns=0)
        assert False
    except ValueError:
        pass


def test_grid_config_to_dict():
    grid = GridConfig(rows=5, columns=5)
    d = grid.to_dict()
    assert d == {"rows": 5, "columns": 5}


# ── Panel tests ────────────────────────────────────────────────────────

def test_panel_config_holds_components():
    panel = PanelConfig(
        panel_id="main",
        name="Main",
        components={
            "board": ComponentConfig(name="Board"),
            "token": ComponentConfig(name="Token", shape="circle"),
        },
    )
    assert len(panel.components) == 2
    assert panel.components["token"].shape == "circle"


def test_panel_config_normalizes_dict_components():
    panel = PanelConfig(
        panel_id="main",
        name="Main",
        components={"board": {"name": "Board", "shape": "rectangle"}},
    )
    assert isinstance(panel.components["board"], ComponentConfig)


def test_panel_empty_name_rejected():
    try:
        PanelConfig(panel_id="x", name="")
        assert False
    except ValueError:
        pass


# ── Confirm tests ──────────────────────────────────────────────────────

def test_confirm_config_defaults():
    c = ConfirmConfig()
    assert c.required is False
    assert c.name == "Confirm"
    assert c.description == ""


def test_confirm_config_to_dict():
    c = ConfirmConfig(required=True, name="Go", description="End turn")
    d = c.to_dict()
    assert d["required"] is True
    assert d["name"] == "Go"
    assert d["description"] == "End turn"


def test_confirm_config_false_is_valid():
    c = ConfirmConfig(required=False)
    assert c.required is False


# ── Phase tests ────────────────────────────────────────────────────────

def test_phase_config_minimal():
    p = PhaseConfig(name="Move")
    assert p.name == "Move"
    assert p.text == ""
    assert p.order == 0
    assert p.confirm is None
    assert p.timeout_seconds is None


def test_phase_config_full():
    p = PhaseConfig(
        name="Pass_Turn",
        text="Confirm your move",
        order=2,
        confirm=ConfirmConfig(required=True, name="Confirm", description="End turn"),
        timeout_seconds=30,
    )
    assert p.confirm.required is True
    assert p.timeout_seconds == 30


def test_phase_config_normalizes_dict_confirm():
    p = PhaseConfig(
        name="Test",
        confirm={"required": True, "name": "OK"},
    )
    assert isinstance(p.confirm, ConfirmConfig)
    assert p.confirm.name == "OK"


def test_phase_empty_name_rejected():
    try:
        PhaseConfig(name="")
        assert False
    except ValueError as e:
        assert "phase name must be non-empty" in str(e)


def test_phase_to_dict():
    p = PhaseConfig(
        name="Move",
        text="Make a move",
        order=1,
        confirm=ConfirmConfig(required=False),
    )
    d = p.to_dict()
    assert d["name"] == "Move"
    assert d["text"] == "Make a move"
    assert d["order"] == 1
    assert d["confirm"]["required"] is False


# ── Turn tests ─────────────────────────────────────────────────────────

def test_turn_config_minimal():
    t = TurnConfig(name="Player Turn")
    assert t.name == "Player Turn"
    assert t.phases == []


def test_turn_config_with_phases():
    t = TurnConfig(
        name="Player Turn",
        phases=[
            PhaseConfig(name="Move", order=1),
            PhaseConfig(name="Confirm", order=2),
        ],
    )
    assert len(t.phases) == 2
    assert t.phases[0].name == "Move"
    assert t.phases[1].name == "Confirm"


def test_turn_config_normalizes_dict_phases():
    t = TurnConfig(
        name="Turn",
        phases=[
            {"name": "Phase1", "order": 1},
            {"name": "Phase2", "order": 2},
        ],
    )
    assert all(isinstance(p, PhaseConfig) for p in t.phases)


def test_turn_empty_name_rejected():
    try:
        TurnConfig(name="")
        assert False
    except ValueError:
        pass


def test_turn_to_dict():
    t = TurnConfig(
        name="Turn",
        phases=[PhaseConfig(name="P1", order=1)],
    )
    d = t.to_dict()
    assert d["name"] == "Turn"
    assert len(d["phases"]) == 1
    assert d["phases"][0]["name"] == "P1"


# ── Round tests ────────────────────────────────────────────────────────

def test_round_config_minimal():
    r = RoundConfig(name="Main Game")
    assert r.name == "Main Game"
    assert r.turns == []


def test_round_config_with_turns():
    r = RoundConfig(
        name="Main Game",
        turns=[
            TurnConfig(name="Player Turn", phases=[
                PhaseConfig(name="Move"),
                PhaseConfig(name="Confirm"),
            ]),
        ],
    )
    assert len(r.turns) == 1
    assert len(r.turns[0].phases) == 2


def test_round_config_normalizes_dict_turns():
    r = RoundConfig(
        name="Round",
        turns=[
            {"name": "Turn1", "phases": [{"name": "P1"}]},
        ],
    )
    assert all(isinstance(t, TurnConfig) for t in r.turns)


def test_round_empty_name_rejected():
    try:
        RoundConfig(name="")
        assert False
    except ValueError:
        pass


# ── GameConfig tests ──────────────────────────────────────────────────

def test_game_config_requires_game_progress_panel():
    try:
        GameConfig(panels={
            "main_board": PanelConfig(panel_id="main_board", name="Board"),
        }, rounds=[])
        assert False
    except ValueError as e:
        assert "game_progress" in str(e).lower()


def test_game_config_requires_main_board_panel():
    try:
        GameConfig(panels={
            "game_progress": PanelConfig(panel_id="game_progress", name="Progress"),
        }, rounds=[])
        assert False
    except ValueError as e:
        assert "main_board" in str(e).lower()


def test_game_config_full():
    config = GameConfig(
        panels={
            "game_progress": PanelConfig(panel_id="game_progress", name="Progress"),
            "main_board": PanelConfig(
                panel_id="main_board",
                name="Board",
                components={
                    "board": ComponentConfig(name="Board", grid=GridConfig(rows=8, columns=8)),
                },
            ),
        },
        rounds=[
            RoundConfig(name="Main Game", turns=[
                TurnConfig(name="Player Turn", phases=[
                    PhaseConfig(name="Move", order=1),
                    PhaseConfig(name="Confirm", order=2, confirm=ConfirmConfig(required=True)),
                ]),
            ]),
        ],
    )
    assert config is not None
    assert len(config.rounds) == 1
    assert len(config.rounds[0].turns[0].phases) == 2


def test_game_config_to_dict_round_trip():
    config = GameConfig(
        panels={
            "game_progress": PanelConfig(panel_id="game_progress", name="Progress"),
            "main_board": PanelConfig(panel_id="main_board", name="Board"),
        },
        rounds=[
            RoundConfig(name="R1", turns=[
                TurnConfig(name="T1", phases=[
                    PhaseConfig(name="P1", order=1),
                ]),
            ]),
        ],
    )
    d = config.to_dict()
    assert "panels" in d
    assert "rounds" in d
    assert d["rounds"][0]["name"] == "R1"
    assert d["rounds"][0]["turns"][0]["phases"][0]["name"] == "P1"
