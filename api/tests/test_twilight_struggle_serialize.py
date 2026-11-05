from __future__ import annotations

from app.games.twilight_struggle.serialize import serialize_game_state


def test_serialization_only_exposes_viewers_hand_and_hides_future_information() -> None:
    state = {
        "countries": {"Italy": {"us": 2, "ussr": 0}},
        "hands": {"us": ["US Secret"], "ussr": ["Soviet Secret"]},
        "draw_pile": ["Top card", "Next card"],
        "headline_cards": {"us": "Secret headline", "ussr": None},
        "_rng_state_json": "secret rng payload",
        "rng_seed": 1234,
        "turn": 3,
        "tracks": {"defcon": 4},
    }

    us_view = serialize_game_state(state, "us")
    ussr_view = serialize_game_state(state, "ussr")
    observer_view = serialize_game_state(state, "not-a-faction")

    assert us_view["hand"] == ["US Secret"]
    assert ussr_view["hand"] == ["Soviet Secret"]
    assert observer_view["hand"] is None
    for view in (us_view, ussr_view, observer_view):
        assert view["hand_count"] == {"us": 1, "ussr": 1}
        assert view["draw_pile_count"] == 2
        assert "draw_pile" not in view
        assert "headline_cards" not in view
        assert "rng_seed" not in view
        assert "_rng_state_json" not in view
    assert us_view["headline_committed"] == {"us": True, "ussr": False}
    assert us_view["countries"] == state["countries"]


def test_serialized_view_is_detached_from_authoritative_state() -> None:
    state = {"hands": {"us": ["card"], "ussr": []}, "countries": {}}
    result = serialize_game_state(state, "us")
    result["hand"].clear()
    assert state["hands"]["us"] == ["card"]


