from __future__ import annotations

from app.games.twilight_struggle.state import create_initial_game_data


def test_initial_state_uses_configured_country_graph_and_setup_totals() -> None:
    state = create_initial_game_data(rng_seed=17)

    assert state["rules_edition"] == "twilight_struggle_2nd_edition"
    assert state["ready_to_play"] is False
    assert state["rng_seed"] == 17
    assert "China" not in state["countries"]
    assert state["countries"]["Canada"] == {"us": 2, "ussr": 0}
    assert state["countries"]["U.K."] == {"us": 5, "ussr": 0}
    assert state["countries"]["E. Germany"] == {"us": 0, "ussr": 3}
    assert sum(item["us"] for item in state["countries"].values()) == 25
    assert sum(item["ussr"] for item in state["countries"].values()) == 15
    assert state["tracks"]["defcon"] == 5
    assert state["china_card"] == {"owner": "ussr", "face_up": True}
    assert len(state["hands"]["us"]) == len(state["hands"]["ussr"]) == 8
    assert state["current_phase"] == "headline"
    assert state["ready_to_play"] is False
    card_ids = [card["id"] for hand in state["hands"].values() for card in hand]
    card_ids.extend(card["id"] for card in state["draw_pile"])
    assert len(card_ids) == len(set(card_ids))
    # Early-war pool: 35 base cards minus China Card, plus VASSAL era-1 cards 103-106 (38 total).
    assert len(card_ids) == 38
    assert len(state["draw_pile"]) == 22
    assert state["rng_state_json"] != "{}"


def test_initial_state_is_fresh_for_each_session() -> None:
    first = create_initial_game_data()
    second = create_initial_game_data()

    first["countries"]["Canada"]["us"] = 99
    first["tracks"]["military_operations"]["us"] = 99
    first["hands"]["us"].clear()
    assert second["countries"]["Canada"]["us"] == 2
    assert second["tracks"]["military_operations"]["us"] == 0
    assert len(second["hands"]["us"]) == 8
