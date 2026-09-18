"""Tests for GameState and Move Pydantic envelope."""

from app.core.game_state import (
    BoardSpace,
    ComponentInstance,
    GameState,
    Move,
    Panel,
    PlayerInfo,
    TrackMeter,
    Topology,
    TurnInfo,
    to_player_view,
)


def test_minimal_game_state_round_trip():
    """Verify a minimal GameState can be created, serialized, and deserialized round-trip."""
    topology = Topology.grid
    player = PlayerInfo(player_id="p1", name="Alice", score=10, color="#FF0000")
    turn = TurnInfo(turn_id="t1", player_id="p1", topology=topology, actions_remaining=2)
    space = BoardSpace(x=0, y=0, topology=topology)
    move = Move(
        move_id="m1",
        player_id="p1",
        topology=topology,
        from_space=space,
        to_space=BoardSpace(x=1, y=1, topology=topology),
    )

    gs = GameState(
        state_id="s1",
        game_type="test_game",
        topology=topology,
        rng_seed=12345,
        rng_state_json='{"state": "test"}',
        players=[player],
        current_player_index=0,
        turn=turn,
    )
    gs.move_history.append(move)

    gs_dict = gs.model_dump()
    gs2 = GameState.model_validate(gs_dict)

    assert gs2.state_id == gs.state_id
    assert gs2.game_type == gs.game_type
    assert gs2.topology == gs.topology
    assert gs2.rng_seed == gs.rng_seed
    assert gs2.rng_state_json == gs.rng_state_json
    assert len(gs2.players) == 1
    assert gs2.players[0].player_id == "p1"
    assert gs2.current_player_index == 0
    assert gs2.turn.turn_id == gs.turn.turn_id
    assert len(gs2.move_history) == 1
    assert gs2.move_history[0].move_id == move.move_id


def test_game_state_multi_player():
    """Verify GameState supports multiple players."""
    p1 = PlayerInfo(player_id="p1", name="Alice", color="#FF0000")
    p2 = PlayerInfo(player_id="p2", name="Bob", color="#0000FF")
    turn = TurnInfo(turn_id="t1", player_id="p1", topology=Topology.grid)

    gs = GameState(
        state_id="s1",
        game_type="checkers",
        players=[p1, p2],
        current_player_index=0,
        turn=turn,
    )

    assert len(gs.players) == 2
    assert gs.current_player.player_id == "p1"
    assert gs.current_player_id == "p1"

    gs.current_player_index = 1
    assert gs.current_player.player_id == "p2"
    assert gs.current_player_id == "p2"


def test_game_state_game_data():
    """Verify game_data field stores arbitrary game-specific state."""
    turn = TurnInfo(turn_id="t1", player_id="p1", topology=Topology.grid)
    gs = GameState(
        state_id="s1",
        game_type="checkers",
        players=[PlayerInfo(player_id="p1", name="Alice")],
        turn=turn,
        game_data={"board": {"(0,0)": "red_piece"}, "size": 8},
    )

    assert gs.game_data["board"]["(0,0)"] == "red_piece"
    assert gs.game_data["size"] == 8


def test_invalid_topology_rejected():
    """Verify that invalid topology values are rejected by models that use Topology."""
    invalid_topologies = ["square", "circular", "network", "map", "grid "]

    for invalid in invalid_topologies:
        try:
            TurnInfo(turn_id="t1", player_id="p1", topology=invalid)  # type: ignore
            assert False, f"TurnInfo should reject topology={invalid!r}"
        except Exception:
            pass

        try:
            BoardSpace(x=0, y=0, topology=invalid)  # type: ignore
            assert False, f"BoardSpace should reject topology={invalid!r}"
        except Exception:
            pass

        try:
            Panel(panel_id="p1", name="Test", topology=invalid)  # type: ignore
            assert False, f"Panel should reject topology={invalid!r}"
        except Exception:
            pass

        try:
            ComponentInstance(
                component_id="c1", component_type="test", topology=invalid  # type: ignore
            )
            assert False, f"ComponentInstance should reject topology={invalid!r}"
        except Exception:
            pass

        try:
            Move(
                move_id="m1",
                player_id="p1",
                topology=invalid,  # type: ignore
            )
            assert False, f"Move should reject topology={invalid!r}"
        except Exception:
            pass


def test_component_type_enum_enforced():
    """Verify that ComponentInstance enforces valid component types."""
    valid_types = {"unit", "building", "terrain", "resource"}
    invalid_types = {"inv@lid", "", "123", "space ship"}

    for ct in valid_types:
        ci = ComponentInstance(
            component_id="c1",
            component_type=ct,
            topology=Topology.grid,
            position=BoardSpace(x=0, y=0, topology=Topology.grid),
            owner_id="p1",
            hidden=False,
        )
        assert ci.component_type == ct

    for ct in invalid_types:
        try:
            ComponentInstance(
                component_id="c1",
                component_type=ct,
                topology=Topology.grid,
                position=BoardSpace(x=0, y=0, topology=Topology.grid),
                owner_id="p1",
                hidden=False,
            )
            assert False, f"ComponentInstance should reject component_type={ct!r}"
        except Exception:
            pass


def test_to_player_view_strips_other_players_private():
    """Verify that to_player_view strips private data for other players."""
    topology = Topology.grid
    player1 = PlayerInfo(player_id="p1", name="Alice", score=10, color="#FF0000")
    player2 = PlayerInfo(player_id="p2", name="Bob", score=5, color="#0000FF")
    turn = TurnInfo(turn_id="t1", player_id="p1", topology=topology, actions_remaining=2)
    space = BoardSpace(x=0, y=0, topology=topology)
    comp = ComponentInstance(
        component_id="c1",
        component_type="unit",
        topology=topology,
        position=space,
        owner_id="p1",
        hidden=False,
    )
    gs = GameState(
        state_id="s1",
        topology=topology,
        rng_seed=12345,
        rng_state_json='{"state": "test"}',
        players=[player1, player2],
        current_player_index=0,
        turn=turn,
    )
    gs.components["c1"] = comp

    # View as p2: p1's private data should be stripped
    viewed = to_player_view(gs, viewer_id="p2")

    # p1 should be stripped
    p1_viewed = [p for p in viewed.players if p.player_id == "p1"][0]
    assert p1_viewed.name == ""
    assert p1_viewed.score == 0
    assert p1_viewed.color == "#000000"
    # p2 should be fully visible
    p2_viewed = [p for p in viewed.players if p.player_id == "p2"][0]
    assert p2_viewed.name == "Bob"
    assert p2_viewed.score == 5
    # Component presence should be kept
    assert "c1" in viewed.components


def test_to_player_view_redacts_hidden_component_for_non_owner():
    """Verify that to_player_view redacts hidden components for non-owners."""
    topology = Topology.grid
    player1 = PlayerInfo(player_id="p1", name="Alice", score=10, color="#FF0000")
    player2 = PlayerInfo(player_id="p2", name="Bob", score=5, color="#0000FF")
    turn = TurnInfo(turn_id="t1", player_id="p1", topology=topology, actions_remaining=2)
    space = BoardSpace(x=0, y=0, topology=topology)
    hidden_comp = ComponentInstance(
        component_id="c1",
        component_type="building",
        topology=topology,
        position=space,
        owner_id="p1",
        hidden=True,
    )
    visible_comp = ComponentInstance(
        component_id="c2",
        component_type="terrain",
        topology=topology,
        position=BoardSpace(x=1, y=1, topology=topology),
        owner_id="p1",
        hidden=False,
    )
    gs = GameState(
        state_id="s1",
        topology=topology,
        rng_seed=12345,
        rng_state_json='{"state": "test"}',
        players=[player1, player2],
        current_player_index=0,
        turn=turn,
    )
    gs.components["c1"] = hidden_comp
    gs.components["c2"] = visible_comp

    # View as p2 (non-owner): hidden component should be redacted
    viewed = to_player_view(gs, viewer_id="p2")

    assert "c1" in viewed.components
    assert viewed.components["c1"].hp == 0
    assert "c2" in viewed.components
    assert viewed.components["c2"].hp == 10


def test_to_player_view_leaves_public_components_untouched():
    """Verify that to_player_view leaves public components untouched for any viewer."""
    topology = Topology.grid
    player1 = PlayerInfo(player_id="p1", name="Alice", score=10, color="#FF0000")
    player2 = PlayerInfo(player_id="p2", name="Bob", score=5, color="#0000FF")
    turn = TurnInfo(turn_id="t1", player_id="p1", topology=topology, actions_remaining=2)
    space = BoardSpace(x=0, y=0, topology=topology)
    public_comp = ComponentInstance(
        component_id="c1",
        component_type="unit",
        topology=topology,
        position=space,
        owner_id="p1",
        hidden=False,
    )
    gs = GameState(
        state_id="s1",
        topology=topology,
        rng_seed=12345,
        rng_state_json='{"state": "test"}',
        players=[player1, player2],
        current_player_index=0,
        turn=turn,
    )
    gs.components["c1"] = public_comp

    # View as p2: public component should be fully visible
    viewed = to_player_view(gs, viewer_id="p2")
    assert "c1" in viewed.components
    assert viewed.components["c1"].component_type == "unit"
    assert viewed.components["c1"].hp == 10
    # View as p1: should also work
    viewed_self = to_player_view(gs, viewer_id="p1")
    assert "c1" in viewed_self.components
    assert viewed_self.components["c1"].component_type == "unit"
