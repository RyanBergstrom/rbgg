from copy import deepcopy
import random

import pytest

from app.games.twilight_struggle.events import apply_event_effects, resolve_card_event


@pytest.fixture
def state_and_countries():
    return (
        {
            "countries": {"Canada": {"us": 1, "ussr": 0}},
            "tracks": {"victory_points": 0, "defcon": 4},
            "persistent_events": {},
            "china_card": {"owner": "ussr", "face_up": False},
        },
        {"countries": {"Canada": {}}},
    )


def test_applies_structured_effects_without_mutating_input(state_and_countries):
    original, countries = state_and_countries
    before = deepcopy(original)
    result = apply_event_effects(
        original,
        [
            {"type": "add_influence", "faction": "ussr", "country": "Canada", "amount": 2},
            {"type": "gain_vp", "faction": "us", "amount": 3},
            {"type": "adjust_defcon", "amount": -1},
            {"type": "set_persistent_event", "name": "test_event", "active": True},
            {"type": "transfer_china_card", "owner": "us"},
        ],
        countries,
    )
    assert original == before
    assert result["countries"]["Canada"]["ussr"] == 2
    assert result["tracks"] == {"victory_points": 3, "defcon": 3}
    assert result["persistent_events"] == {"test_event": True}
    assert result["china_card"] == {"owner": "us", "face_up": True}


def test_rejects_unknown_effect_atomically(state_and_countries):
    original, countries = state_and_countries
    with pytest.raises(ValueError, match="Unsupported"):
        apply_event_effects(
            original,
            [{"type": "gain_vp", "faction": "us", "amount": 1}, {"type": "unknown"}],
            countries,
        )
    assert original["tracks"]["victory_points"] == 0


def test_rejects_unknown_country(state_and_countries):
    original, countries = state_and_countries
    with pytest.raises(ValueError, match="Unknown event target country"):
        apply_event_effects(
            original,
            [{"type": "add_influence", "faction": "us", "country": "Atlantis", "amount": 1}],
            countries,
        )


def test_duck_and_cover_resolves_opponent_event_and_applies_defcon_vp():
    game_data = {
        "countries": {},
        "tracks": {"defcon": 5, "victory_points": 0},
        "persistent_events": {},
    }
    card = {
        "id": 4,
        "name": "Duck and Cover",
        "alignment": "us",
        "effect_handler": "duck_and_cover",
    }

    result = resolve_card_event(game_data, card, "ussr", mode="operations")

    assert result["event_triggered"] is True
    assert result["game_data"]["tracks"] == {"defcon": 4, "victory_points": 1}
    assert result["terminal_result"] is None
    assert game_data["tracks"]["defcon"] == 5


def test_duck_and_cover_defcon_one_ends_for_phasing_player():
    game_data = {
        "countries": {},
        "tracks": {"defcon": 2, "victory_points": 0},
        "persistent_events": {},
    }
    card = {"id": 4, "alignment": "us", "effect_handler": "duck_and_cover"}
    result = resolve_card_event(game_data, card, "ussr", mode="operations")

    assert result["game_data"]["tracks"]["defcon"] == 1
    # Nuclear war ends immediately; Duck and Cover's subsequent VP award never occurs.
    assert result["game_data"]["tracks"]["victory_points"] == 0
    assert result["terminal_result"] == {"winner": "us", "reason": "defcon_1"}


def test_unimplemented_mandatory_event_fails_closed():
    card = {"id": 6, "name": "The China Card", "alignment": "both", "effect_handler": None}
    with pytest.raises(ValueError, match="No implemented event handler"):
        resolve_card_event(
            {"tracks": {"defcon": 5, "victory_points": 0}},
            card,
            "ussr",
            mode="operations",
        )


def test_five_year_plan_randomly_discards_and_triggers_us_event():
    from app.games.twilight_struggle.country_data import load_country_data

    game_data = {
        "hands": {
            "us": [],
            "ussr": [{"id": 4, "name": "Duck and Cover", "alignment": "us", "scoring": False, "event_removed": False, "effect_handler": "duck_and_cover"}],
        },
        "countries": {},
        "tracks": {"defcon": 5, "victory_points": 0},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
    }
    card = {"id": 5, "name": "Five Year Plan", "alignment": "us", "effect_handler": "five_year_plan"}

    result = resolve_card_event(
        game_data, card, "ussr", mode="operations", rng=random.Random(7),
        country_data=load_country_data(),
    )

    assert result["event_triggered"] is True
    assert result["game_data"]["hands"]["ussr"] == []
    assert result["game_data"]["discard_pile"][0]["id"] == 4
    assert result["game_data"]["tracks"] == {"defcon": 4, "victory_points": 1}
    assert game_data["hands"]["ussr"][0]["id"] == 4


def test_five_year_plan_is_prevented_when_ussr_hand_is_empty():
    from app.games.twilight_struggle.country_data import load_country_data

    card = {"id": 5, "name": "Five Year Plan", "alignment": "us", "effect_handler": "five_year_plan"}
    state = {"hands": {"us": [], "ussr": []}, "tracks": {"defcon": 5, "victory_points": 0}}

    result = resolve_card_event(
        state, card, "ussr", mode="operations", rng=random.Random(0),
        country_data=load_country_data(),
    )

    assert result["event_triggered"] is False
    assert result["game_data"] == state


def test_nested_event_cycle_stops_when_a_card_repeats_on_the_active_chain():
    star_wars = {
        "id": 85, "name": "Star Wars", "alignment": "us", "operations": 2,
        "effect_handler": "star_wars",
    }
    missile_envy = {
        "id": 49, "name": "Missile Envy", "alignment": "both", "operations": 2,
        "effect_handler": "missile_envy",
    }
    game = _base_game(
        tracks={"defcon": 5, "victory_points": 0, "space_race": {"us": 2, "ussr": 1}},
        hands={"us": [], "ussr": [star_wars.copy()]},
        discard_pile=[missile_envy],
    )

    result = resolve_card_event(
        game, star_wars, "us", mode="event", event_choices={"star_wars": 49},
    )

    assert result["event_triggered"] is True
    assert [card["id"] for card in result["game_data"]["discard_pile"]] == [85, 49]
    assert game["hands"]["ussr"][0]["id"] == 85


def _base_game(**overrides):
    game = {
        "hands": {"us": [], "ussr": []},
        "countries": {},
        "tracks": {"defcon": 3, "victory_points": 0},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }
    game.update(overrides)
    return game


def test_abm_treaty_improves_defcon_one_level():
    card = {"id": 57, "name": "ABM Treaty", "alignment": "both", "effect_handler": "abm_treaty"}
    result = resolve_card_event(_base_game(), card, "us", mode="event")
    assert result["event_triggered"] is True
    assert result["game_data"]["tracks"]["defcon"] == 4


def test_nixon_plays_china_gains_vp_when_us_already_holds_china_card():
    card = {"id": 71, "name": "Nixon Plays the China Card", "alignment": "us", "effect_handler": "nixon_plays_china"}
    game = _base_game(china_card={"owner": "us", "face_up": True})
    result = resolve_card_event(game, card, "us", mode="event")
    assert result["game_data"]["tracks"]["victory_points"] == 2
    assert result["game_data"]["china_card"] == {"owner": "us", "face_up": True}


def test_nixon_plays_china_takes_china_card_face_down_from_ussr():
    card = {"id": 71, "name": "Nixon Plays the China Card", "alignment": "us", "effect_handler": "nixon_plays_china"}
    result = resolve_card_event(_base_game(), card, "us", mode="event")
    assert result["game_data"]["tracks"]["victory_points"] == 0
    assert result["game_data"]["china_card"] == {"owner": "us", "face_up": False}


def test_terrorism_ussr_play_makes_us_discard_two_with_iran_hostage_crisis():
    card = {"id": 92, "name": "Terrorism", "alignment": "both", "effect_handler": "terrorism"}
    us_cards = [{"id": 10}, {"id": 11}, {"id": 12}]
    game = _base_game(
        hands={"us": list(us_cards), "ussr": []},
        persistent_events={"iranian_hostage_crisis": True},
    )
    result = resolve_card_event(game, card, "ussr", mode="event", rng=random.Random(3))
    new_state = result["game_data"]
    assert len(new_state["hands"]["us"]) == 1
    assert len(new_state["discard_pile"]) == 2
    assert {c["id"] for c in new_state["discard_pile"]} <= {10, 11, 12}
    assert len(game["hands"]["us"]) == 3


def test_terrorism_us_play_makes_ussr_discard_one_card():
    card = {"id": 92, "name": "Terrorism", "alignment": "both", "effect_handler": "terrorism"}
    game = _base_game(hands={"us": [], "ussr": [{"id": 20}, {"id": 21}]})
    result = resolve_card_event(game, card, "us", mode="event", rng=random.Random(1))
    assert len(result["game_data"]["hands"]["ussr"]) == 1
    assert len(result["game_data"]["discard_pile"]) == 1


def test_terrorism_requires_server_rng():
    card = {"id": 92, "name": "Terrorism", "alignment": "both", "effect_handler": "terrorism"}
    with pytest.raises(ValueError, match="server RNG"):
        resolve_card_event(_base_game(), card, "us", mode="event")


def test_aldrich_ames_remix_discards_selected_us_card():
    card = {"id": 98, "name": "Aldrich Ames Remix", "alignment": "ussr", "effect_handler": "aldrich_ames_remix"}
    game = _base_game(hands={"us": [{"id": 10}, {"id": 11}], "ussr": []})
    result = resolve_card_event(
        game, card, "ussr", mode="event", event_choices={"aldrich_ames_remix": 10},
    )
    assert [c["id"] for c in result["game_data"]["hands"]["us"]] == [11]
    assert [c["id"] for c in result["game_data"]["discard_pile"]] == [10]
    assert len(game["hands"]["us"]) == 2


def test_aldrich_ames_remix_rejects_card_not_in_us_hand():
    card = {"id": 98, "name": "Aldrich Ames Remix", "alignment": "ussr", "effect_handler": "aldrich_ames_remix"}
    game = _base_game(hands={"us": [{"id": 10}], "ussr": []})
    with pytest.raises(ValueError, match="US hand"):
        resolve_card_event(game, card, "ussr", mode="event", event_choices={"aldrich_ames_remix": 99})


def _full_board(country_data, **us_influence):
    board = {name: {"us": 0, "ussr": 0} for name in country_data["countries"]}
    for name, amount in us_influence.items():
        board[name.replace("_", " ")]["us"] = amount
    return board


def test_muslim_revolution_removes_all_us_influence_in_two_chosen_countries():
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    card = {"id": 56, "name": "Muslim Revolution", "alignment": "ussr", "effect_handler": "muslim_revolution"}
    game = _base_game(countries=_full_board(data, Iraq=2, Egypt=1, Libya=3))
    result = resolve_card_event(
        game, card, "ussr", mode="event", country_data=data,
        event_choices={"muslim_revolution": ["Iraq", "Egypt"]},
    )
    board = result["game_data"]["countries"]
    assert board["Iraq"]["us"] == 0
    assert board["Egypt"]["us"] == 0
    assert board["Libya"]["us"] == 3


def test_muslim_revolution_rejects_duplicate_or_unlisted_countries():
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    card = {"id": 56, "name": "Muslim Revolution", "alignment": "ussr", "effect_handler": "muslim_revolution"}
    game = _base_game(countries=_full_board(data))
    for bad in (["Iraq", "Iraq"], ["Iraq", "France"], ["Iraq"]):
        with pytest.raises(ValueError, match="Muslim Revolution"):
            resolve_card_event(
                game, card, "ussr", mode="event", country_data=data,
                event_choices={"muslim_revolution": bad},
            )


def test_muslim_revolution_blocked_after_awacs_sale_flag():
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    card = {"id": 56, "name": "Muslim Revolution", "alignment": "ussr", "effect_handler": "muslim_revolution"}
    game = _base_game(
        countries=_full_board(data),
        persistent_events={"awacs_sale_played": True},
    )
    with pytest.raises(ValueError, match="AWACS"):
        resolve_card_event(
            game, card, "ussr", mode="event", country_data=data,
            event_choices={"muslim_revolution": ["Iraq", "Egypt"]},
        )


def test_awacs_sale_adds_us_influence_to_saudi_arabia_and_sets_flag():
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    card = {"id": 110, "name": "AWACS Sale to Saudis*", "alignment": "us", "effect_handler": "awacs_sale_to_saudis"}
    game = _base_game(countries=_full_board(data, Saudi_Arabia=1))
    result = resolve_card_event(game, card, "us", mode="event", country_data=data)

    assert result["event_triggered"] is True
    assert result["game_data"]["countries"]["Saudi Arabia"]["us"] == 3
    assert result["game_data"]["persistent_events"]["awacs_sale_played"] is True
    assert game["countries"]["Saudi Arabia"]["us"] == 1
    assert "awacs_sale_played" not in game["persistent_events"]


def test_awacs_sale_then_muslim_revolution_is_blocked():
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    awacs = {"id": 110, "name": "AWACS Sale to Saudis*", "alignment": "us", "effect_handler": "awacs_sale_to_saudis"}
    muslim = {"id": 56, "name": "Muslim Revolution", "alignment": "ussr", "effect_handler": "muslim_revolution"}
    after_awacs = resolve_card_event(_base_game(countries=_full_board(data)), awacs, "us", mode="event", country_data=data)["game_data"]
    with pytest.raises(ValueError, match="AWACS"):
        resolve_card_event(
            after_awacs, muslim, "ussr", mode="event", country_data=data,
            event_choices={"muslim_revolution": ["Iraq", "Egypt"]},
        )


@pytest.mark.parametrize(
    ("card_id", "country", "before", "expected"),
    [
        (8, "Cuba", {"us": 3, "ussr": 1}, {"us": 0, "ussr": 3}),
        (12, "Romania", {"us": 1, "ussr": 0}, {"us": 0, "ussr": 3}),
        (15, "Egypt", {"us": 3, "ussr": 1}, {"us": 1, "ussr": 3}),
    ],
)
def test_deterministic_early_war_influence_events(card_id, country, before, expected):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries[country] = dict(before)
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    result = resolve_card_event(
        state, card, "us", mode="event", country_data=data
    )

    assert result["event_triggered"] is True
    assert result["game_data"]["countries"][country] == expected
    assert state["countries"][country] == before


@pytest.mark.parametrize(
    ("faction", "expected_vp"),
    [("us", 2), ("ussr", -2)],
)
def test_nuclear_test_ban_uses_current_defcon_and_phasing_faction(faction, expected_vp):
    from app.games.twilight_struggle.cards import load_standard_card_catalog

    card = next(item for item in load_standard_card_catalog() if item["id"] == 34)
    state = {"tracks": {"defcon": 4, "victory_points": 0}}

    result = resolve_card_event(state, card, faction, mode="event")

    assert result["game_data"]["tracks"] == {"defcon": 5, "victory_points": expected_vp}


@pytest.mark.parametrize(
    ("card_id", "faction", "event_name", "expected_faction"),
    [
        (25, "us", "containment", "us"),
        (31, "us", "red_scare_purge", "ussr"),
    ],
)
def test_turn_scoped_ops_events_set_correct_target(card_id, faction, event_name, expected_faction):
    from app.games.twilight_struggle.cards import load_standard_card_catalog

    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"turn": 4, "persistent_events": {}, "tracks": {"defcon": 5, "victory_points": 0}}

    result = resolve_card_event(state, card, faction, mode="event")

    assert result["game_data"]["persistent_events"][event_name] == {
        "faction": expected_faction,
        "expires_turn": 4,
    }


def test_how_i_learned_to_stop_worrying_sets_selected_defcon_and_five_milops():
    from app.games.twilight_struggle.cards import load_standard_card_catalog

    card = next(item for item in load_standard_card_catalog() if item["id"] == 46)
    state = {"tracks": {"defcon": 4, "victory_points": 0, "military_operations": {"us": 1, "ussr": 2}}}
    result = resolve_card_event(state, card, "ussr", mode="event", chosen_defcon=2)

    assert result["game_data"]["tracks"]["defcon"] == 2
    assert result["game_data"]["tracks"]["military_operations"] == {"us": 1, "ussr": 5}
    with pytest.raises(ValueError, match="chosen_defcon"):
        resolve_card_event(state, card, "ussr", mode="event", chosen_defcon=6)


@pytest.mark.parametrize(
    ("faction", "us_battlegrounds", "ussr_battlegrounds", "expected_vp"),
    [("us", 2, 1, 2), ("ussr", 1, 2, -2), ("us", 1, 1, 0)],
)
def test_kitchen_debates_scores_only_with_battleground_lead(
    faction, us_battlegrounds, ussr_battlegrounds, expected_vp
):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    battlegrounds = [name for name, country in data["countries"].items() if country["battleground"]]
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for name in battlegrounds[:us_battlegrounds]:
        countries[name]["us"] = data["countries"][name]["stability"]
    for name in battlegrounds[us_battlegrounds:us_battlegrounds + ussr_battlegrounds]:
        countries[name]["ussr"] = data["countries"][name]["stability"]
    card = next(item for item in load_standard_card_catalog() if item["id"] == 48)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    result = resolve_card_event(state, card, faction, mode="event", country_data=data)

    assert result["game_data"]["tracks"]["victory_points"] == expected_vp


@pytest.mark.parametrize(
    ("card_id", "faction", "expected_vp", "expected_influence"),
    [
        (54, "us", 0, {"Chile": {"us": 0, "ussr": 2}}),
        (65, "ussr", 1, {
            "Israel": {"us": 1, "ussr": 0},
            "Jordan": {"us": 1, "ussr": 0},
            "Egypt": {"us": 1, "ussr": 0},
        }),
    ],
)
def test_mid_war_influence_events(card_id, faction, expected_vp, expected_influence):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    result = resolve_card_event(state, card, faction, mode="event", country_data=data)

    assert result["game_data"]["tracks"]["victory_points"] == expected_vp
    for name, influence in expected_influence.items():
        assert result["game_data"]["countries"][name] == influence
    if card_id == 65:
        assert result["game_data"]["persistent_events"]["arab_israeli_war_cancelled"] is True
    assert state["tracks"]["victory_points"] == 0


@pytest.mark.parametrize(
    ("card_id", "faction", "initial", "expected"),
    [
        (17, "us", {"France": {"us": 3, "ussr": 0}}, {"France": {"us": 1, "ussr": 1}}),
        (52, "us", {}, {
            "SE African States": {"us": 0, "ussr": 2},
            "Angola": {"us": 0, "ussr": 2},
        }),
        (68, "ussr", {"Poland": {"us": 0, "ussr": 3}}, {"Poland": {"us": 1, "ussr": 1}}),
    ],
)
def test_confirmed_mid_war_events_apply_effects_and_persistent_flags(card_id, faction, initial, expected):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries.update({name: dict(influence) for name, influence in initial.items()})
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}, "persistent_events": {}}

    outcome = resolve_card_event(state, card, faction, mode="event", country_data=data)

    assert {name: outcome["game_data"]["countries"][name] for name in expected} == expected
    if card_id == 17:
        assert outcome["game_data"]["persistent_events"]["nato_cancelled_countries"] == ["France"]
    if card_id == 68:
        assert outcome["game_data"]["persistent_events"]["solidarity_enabled"] is True
    assert state["countries"] == countries


def test_solidarity_requires_john_paul_ii_event():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 101)
    state = {"countries": {"Poland": {"us": 0, "ussr": 3}}, "tracks": {"victory_points": 0}}

    with pytest.raises(ValueError, match="requires John Paul II"):
        resolve_card_event(state, card, "ussr", mode="event", country_data=load_country_data())


def test_blockade_removes_all_us_influence_from_west_germany_by_default():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 10)
    state = _base_game(countries={"W. Germany": {"us": 3, "ussr": 1}})
    result = resolve_card_event(state, card, "ussr", mode="event", country_data=load_country_data())
    assert result["event_triggered"] is True
    assert result["game_data"]["countries"]["W. Germany"] == {"us": 0, "ussr": 1}


def test_blockade_us_discard_of_three_plus_ops_card_prevents_removal():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 10)
    discard = {"id": 21, "name": "NATO", "operations": 4}
    state = _base_game(countries={"W. Germany": {"us": 3, "ussr": 0}}, hands={"us": [discard], "ussr": []})
    result = resolve_card_event(
        state, card, "ussr", mode="event", country_data=load_country_data(), event_choices={"blockade": 21}
    )
    assert result["game_data"]["countries"]["W. Germany"]["us"] == 3
    assert result["game_data"]["hands"]["us"] == []
    assert result["game_data"]["discard_pile"][-1]["id"] == 21


def test_blockade_rejects_discard_of_low_ops_card():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 10)
    state = _base_game(hands={"us": [{"id": 3, "name": "Low", "operations": 2}], "ussr": []})
    with pytest.raises(ValueError, match="3\\+ Ops"):
        resolve_card_event(
            state, card, "ussr", mode="event", country_data=load_country_data(), event_choices={"blockade": 3}
        )


def test_nato_event_sets_persistent_flag():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 21)
    state = _base_game()
    result = resolve_card_event(state, card, "us", mode="event", country_data=load_country_data())
    assert result["event_triggered"] is True
    assert "nato" in result["game_data"]["persistent_events"]


def test_nato_blocks_ussr_coup_in_us_controlled_europe():
    from app.games.twilight_struggle.country_data import load_country_data
    from app.games.twilight_struggle.operations import resolve_operations_action

    state = _base_game(countries={"W. Germany": {"us": 5, "ussr": 0}})
    state["persistent_events"] = {"nato": {"faction": "us", "expires_turn": 10}}
    state["tracks"]["defcon"] = 5
    action = {"type": "coup", "country": "W. Germany", "die_roll": 6}
    with pytest.raises(ValueError, match="NATO"):
        resolve_operations_action(state, "ussr", 5, action, country_data=load_country_data())


def test_nato_blocks_ussr_realignment_in_us_controlled_europe():
    from app.games.twilight_struggle.country_data import load_country_data
    from app.games.twilight_struggle.operations import resolve_operations_action

    state = _base_game(countries={"W. Germany": {"us": 5, "ussr": 0}})
    state["persistent_events"] = {"nato": {"faction": "us", "expires_turn": 10}}
    state["tracks"]["defcon"] = 5
    action = {"type": "realignment", "targets": [{"country": "W. Germany", "us_roll": 1, "ussr_roll": 6}]}
    with pytest.raises(ValueError, match="NATO"):
        resolve_operations_action(state, "ussr", 5, action, country_data=load_country_data())


def test_nato_does_not_block_ussr_coup_in_france_after_de_gaulle():
    from app.games.twilight_struggle.country_data import load_country_data
    from app.games.twilight_struggle.operations import resolve_operations_action

    state = _base_game(countries={"France": {"us": 3, "ussr": 0}})
    state["persistent_events"] = {"nato": {"faction": "us", "expires_turn": 10}, "nato_cancelled_countries": ["France"]}
    state["tracks"]["defcon"] = 5
    action = {"type": "coup", "country": "France", "die_roll": 6}
    result = resolve_operations_action(state, "ussr", 5, action, country_data=load_country_data())
    assert result["last_ops_result"]["type"] == "coup"


def test_solidarity_adds_three_us_influence_after_john_paul_ii():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 101)
    state = {
        "countries": {"Poland": {"us": 1, "ussr": 1}},
        "tracks": {"victory_points": 0},
        "persistent_events": {"solidarity_enabled": True},
    }

    outcome = resolve_card_event(state, card, "us", mode="event", country_data=load_country_data())

    assert outcome["game_data"]["countries"]["Poland"] == {"us": 4, "ussr": 1}


@pytest.mark.parametrize(
    ("card_id", "faction", "starting", "expected_country", "expected_vp", "expected_flag"),
    [
        (72, "us", {"Egypt": {"us": 0, "ussr": 4}}, {"Egypt": {"us": 1, "ussr": 0}}, 0, None),
        (82, "ussr", {"Iran": {"us": 3, "ussr": 0}}, {"Iran": {"us": 0, "ussr": 2}}, 0, "iranian_hostage_crisis"),
        (83, "us", {"Argentina": {"us": 0, "ussr": 0}, "U.K.": {"us": 0, "ussr": 4}}, {"Argentina": {"us": 0, "ussr": 1}, "U.K.": {"us": 0, "ussr": 0}}, 1, "socialist_governments_cancelled"),
        (84, "ussr", {"Libya": {"us": 0, "ussr": 5}}, {"Libya": {"us": 0, "ussr": 5}}, 2, None),
    ],
)
def test_confirmed_late_war_events(card_id, faction, starting, expected_country, expected_vp, expected_flag):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries.update({name: dict(influence) for name, influence in starting.items()})
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}, "persistent_events": {}}

    outcome = resolve_card_event(state, card, faction, mode="event", country_data=data)

    assert {name: outcome["game_data"]["countries"][name] for name in expected_country} == expected_country
    assert outcome["game_data"]["tracks"]["victory_points"] == expected_vp
    if expected_flag:
        assert outcome["game_data"]["persistent_events"][expected_flag] is True
    assert state["countries"] == countries


@pytest.mark.parametrize(
    ("card_id", "faction", "starting", "expected_countries", "expected_vp", "expected_flags"),
    [
        (55, "us", {"W. Germany": {"us": 2, "ussr": 0}}, {"W. Germany": {"us": 2, "ussr": 1}}, -1, {"nato_cancelled_countries": ["W. Germany"]}),
        (64, "ussr", {}, {"Panama": {"us": 1, "ussr": 0}, "Costa Rica": {"us": 1, "ussr": 0}, "Venezuela": {"us": 1, "ussr": 0}}, 0, {}),
        (78, "us", {"Panama": {"us": 2, "ussr": 0}}, {"Panama": {"us": 2, "ussr": 0}}, 1, {}),
        (90, "us", {}, {}, -2, {}),
        (97, "ussr", {}, {}, 1, {"flower_power_cancelled": True}),
    ],
)
def test_fixed_choice_free_confirmed_events(card_id, faction, starting, expected_countries, expected_vp, expected_flags):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries.update({name: dict(influence) for name, influence in starting.items()})
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 4, "victory_points": 0}, "persistent_events": {}}

    outcome = resolve_card_event(state, card, faction, mode="event", country_data=data)

    assert {name: outcome["game_data"]["countries"][name] for name in expected_countries} == expected_countries
    assert outcome["game_data"]["tracks"]["victory_points"] == expected_vp
    for flag, value in expected_flags.items():
        assert outcome["game_data"]["persistent_events"][flag] == value


def test_willy_brandt_is_canceled_by_tear_down_this_wall():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 55)
    state = {
        "countries": {"W. Germany": {"us": 0, "ussr": 0}},
        "tracks": {"victory_points": 0},
        "persistent_events": {"tear_down_this_wall": True},
    }

    outcome = resolve_card_event(state, card, "us", mode="event", country_data=load_country_data())

    assert outcome["event_triggered"] is False
    assert outcome["game_data"] == state


def test_pershing_ii_removes_us_influence_only_from_up_to_three_western_european_countries():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 99)
    state = {
        "countries": {"France": {"us": 2, "ussr": 0}, "W. Germany": {"us": 1, "ussr": 0}, "Poland": {"us": 3, "ussr": 0}},
        "tracks": {"victory_points": 0},
    }
    outcome = resolve_card_event(
        state, card, "us", mode="event", country_data=load_country_data(),
        event_choices={"pershing_ii_deployed": ["France", "W. Germany"]},
    )

    assert outcome["game_data"]["tracks"]["victory_points"] == -1
    assert outcome["game_data"]["countries"]["France"]["us"] == 1
    assert outcome["game_data"]["countries"]["W. Germany"]["us"] == 0
    assert outcome["game_data"]["countries"]["Poland"]["us"] == 3


def test_pershing_ii_rejects_non_western_europe_targets():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 99)
    state = {"countries": {"Poland": {"us": 2, "ussr": 0}}, "tracks": {"victory_points": 0}}

    with pytest.raises(ValueError, match="Western European"):
        resolve_card_event(
            state, card, "ussr", mode="event", country_data=load_country_data(),
            event_choices={"pershing_ii_deployed": ["Poland"]},
        )


@pytest.mark.parametrize(
    ("card_id", "turn", "choices", "starting", "expected"),
    [
        (19, 1, {"truman_doctrine": "E. Germany"}, {"E. Germany": {"us": 0, "ussr": 1}}, {"E. Germany": {"us": 0, "ussr": 0}}),
        (29, 8, {"east_european_unrests": ["E. Germany", "Poland", "Hungary"]}, {"E. Germany": {"us": 0, "ussr": 2}, "Poland": {"us": 0, "ussr": 3}, "Hungary": {"us": 0, "ussr": 4}}, {"E. Germany": {"us": 0, "ussr": 0}, "Poland": {"us": 0, "ussr": 1}, "Hungary": {"us": 0, "ussr": 2}}),
        (30, 2, {"decolonization": ["Angola", "Kenya", "Thailand", "Malaysia"]}, {}, {"Angola": {"us": 0, "ussr": 1}, "Kenya": {"us": 0, "ussr": 1}, "Thailand": {"us": 0, "ussr": 1}, "Malaysia": {"us": 0, "ussr": 1}}),
        (63, 2, {"colonial_rearguards": ["Angola", "Kenya", "Thailand", "Malaysia"]}, {}, {"Angola": {"us": 1, "ussr": 0}, "Kenya": {"us": 1, "ussr": 0}, "Thailand": {"us": 1, "ussr": 0}, "Malaysia": {"us": 1, "ussr": 0}}),
        (66, 2, {"puppet_governments": ["Canada", "Mexico", "Brazil"]}, {}, {"Canada": {"us": 1, "ussr": 0}, "Mexico": {"us": 1, "ussr": 0}, "Brazil": {"us": 1, "ussr": 0}}),
    ],
)
def test_selected_country_event_batch(card_id, turn, choices, starting, expected):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries.update({name: dict(influence) for name, influence in starting.items()})
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    outcome = resolve_card_event(
        {"turn": turn, "countries": countries, "tracks": {"defcon": 5, "victory_points": 0}},
        card, "us", mode="event", country_data=data, event_choices=choices,
    )
    assert {name: outcome["game_data"]["countries"][name] for name in expected} == expected


def test_south_african_unrest_supports_adjacent_placement_option():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    neighbor = data["adjacency"]["South Africa"][0]
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    card = next(item for item in load_standard_card_catalog() if item["id"] == 53)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}
    outcome = resolve_card_event(
        state, card, "us", mode="event", country_data=data,
        event_choices={"south_african_unrest": {"mode": "adjacent", "adjacent": {neighbor: 2}}},
    )
    assert outcome["game_data"]["countries"]["South Africa"]["ussr"] == 1
    assert outcome["game_data"]["countries"][neighbor]["ussr"] == 2


@pytest.mark.parametrize(
    ("card_id", "choices"),
    [
        (19, {"truman_doctrine": "France"}),
        (29, {"east_european_unrests": ["E. Germany", "Poland", "France"]}),
        (30, {"decolonization": ["Angola", "Kenya", "Thailand", "Japan"]}),
        (63, {"colonial_rearguards": ["Angola", "Angola", "Thailand", "Malaysia"]}),
        (66, {"puppet_governments": ["Canada", "Canada", "Brazil"]}),
    ],
)
def test_selected_country_event_batch_rejects_invalid_targets(card_id, choices):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    with pytest.raises(ValueError):
        resolve_card_event(
            {"turn": 1, "countries": {**countries, "France": {"us": 3, "ussr": 0}}, "tracks": {"defcon": 5, "victory_points": 0}},
            card, "us", mode="event", country_data=data, event_choices=choices,
        )


@pytest.mark.parametrize(
    ("card_id", "faction", "choices", "starting", "expected"),
    [
        (7, "us", {"socialist_governments": {"France": 2, "Italy": 1}}, {"France": {"us": 2, "ussr": 0}, "Italy": {"us": 2, "ussr": 0}}, {"France": {"us": 0, "ussr": 0}, "Italy": {"us": 1, "ussr": 0}}),
        (16, "ussr", {"warsaw_pact_formed": {"mode": "remove_us", "countries": ["E. Germany", "Poland", "Hungary", "Romania"]}}, {"E. Germany": {"us": 1, "ussr": 0}, "Poland": {"us": 2, "ussr": 0}, "Hungary": {"us": 1, "ussr": 0}, "Romania": {"us": 1, "ussr": 0}}, {"E. Germany": {"us": 0, "ussr": 0}, "Poland": {"us": 0, "ussr": 0}, "Hungary": {"us": 0, "ussr": 0}, "Romania": {"us": 0, "ussr": 0}}),
        (16, "ussr", {"warsaw_pact_formed": {"mode": "add_ussr", "distribution": {"E. Germany": 2, "Poland": 2, "Bulgaria": 1}}}, {}, {"E. Germany": {"us": 0, "ussr": 2}, "Poland": {"us": 0, "ussr": 2}, "Bulgaria": {"us": 0, "ussr": 1}}),
        (22, "ussr", {"independent_reds": "Romania"}, {"Romania": {"us": 1, "ussr": 4}}, {"Romania": {"us": 4, "ussr": 4}}),
        (28, "us", {"suez_crisis": {"France": 2, "U.K.": 1, "Israel": 1}}, {"France": {"us": 2, "ussr": 0}, "U.K.": {"us": 1, "ussr": 0}, "Israel": {"us": 1, "ussr": 0}}, {"France": {"us": 0, "ussr": 0}, "U.K.": {"us": 0, "ussr": 0}, "Israel": {"us": 0, "ussr": 0}}),
    ],
)
def test_early_war_choice_event_batch(card_id, faction, choices, starting, expected):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries.update({name: dict(influence) for name, influence in starting.items()})
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "turn": 1, "tracks": {"defcon": 5, "victory_points": 0}}
    outcome = resolve_card_event(state, card, faction, mode="event", country_data=data, event_choices=choices)
    assert {name: outcome["game_data"]["countries"][name] for name in expected} == expected


def test_socialist_governments_is_blocked_by_iron_lady():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == 7)
    with pytest.raises(ValueError, match="canceled by The Iron Lady"):
        resolve_card_event(
            {"countries": {"France": {"us": 2, "ussr": 0}}, "persistent_events": {"socialist_governments_cancelled": True}},
            card, "ussr", mode="event", country_data=load_country_data(),
            event_choices={"socialist_governments": {"France": 2, "Italy": 1}},
        )


@pytest.mark.parametrize(
    ("faction", "military", "defcon", "expected_vp"),
    [
        ("us", {"us": 4, "ussr": 3}, 4, 3),
        ("ussr", {"us": 2, "ussr": 3}, 4, 1),
        ("us", {"us": 3, "ussr": 3}, 4, 0),
    ],
)
def test_arms_race_scores_by_military_operations_and_defcon(faction, military, defcon, expected_vp):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    card = next(item for item in load_standard_card_catalog() if item["id"] == 39)
    outcome = resolve_card_event(
        {"tracks": {"defcon": defcon, "victory_points": 0, "military_operations": military}},
        card, faction, mode="event",
    )
    expected_delta = expected_vp if faction == "us" else -expected_vp
    assert outcome["game_data"]["tracks"]["victory_points"] == expected_delta


@pytest.mark.parametrize(
    ("owner", "expected_owner", "expected_vp"),
    [("us", "ussr", 0), ("ussr", "ussr", -1)],
)
def test_cultural_revolution_transfers_china_card_or_awards_vp(owner, expected_owner, expected_vp):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    card = next(item for item in load_standard_card_catalog() if item["id"] == 58)
    outcome = resolve_card_event(
        {"china_card": {"owner": owner, "face_up": False}, "tracks": {"defcon": 5, "victory_points": 0}},
        card, "ussr", mode="event",
    )
    expected_face_up = owner == "us"
    assert outcome["game_data"]["china_card"] == {"owner": expected_owner, "face_up": expected_face_up}
    assert outcome["game_data"]["tracks"]["victory_points"] == expected_vp


def test_opec_scores_soviet_controlled_oil_countries_and_is_blocked_by_north_sea_oil():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    for name in ("Egypt", "Iran", "Libya", "Saudi Arabia", "Iraq", "Venezuela"):
        countries[name]["ussr"] = data["countries"][name]["stability"]
    card = next(item for item in load_standard_card_catalog() if item["id"] == 61)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}
    outcome = resolve_card_event(state, card, "us", mode="event", country_data=data)
    assert outcome["game_data"]["tracks"]["victory_points"] == -6
    with pytest.raises(ValueError, match="North Sea Oil"):
        resolve_card_event(
            {**state, "persistent_events": {"north_sea_oil": True}},
            card, "us", mode="event", country_data=data,
        )


@pytest.mark.parametrize(
    ("card_id", "faction", "choices", "expected"),
    [
        (14, "ussr", {"comecon": ["Poland", "Hungary", "Romania", "Bulgaria"]}, {"Poland": 1, "Hungary": 1, "Romania": 1, "Bulgaria": 1}),
        (70, "us", {"oas_founded": {"Panama": 1, "Venezuela": 1}}, {"Panama": 1, "Venezuela": 1}),
        (75, "ussr", {"liberation_theology": {"Nicaragua": 2, "Cuba": 1}}, {"Nicaragua": 2, "Cuba": 1}),
    ],
)
def test_selected_influence_event_choices(card_id, faction, choices, expected):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    outcome = resolve_card_event(
        state, card, faction, mode="event", country_data=data, event_choices=choices,
    )

    side = "ussr" if faction == "ussr" else "us"
    assert {name: outcome["game_data"]["countries"][name][side] for name in expected} == expected
    assert all(outcome["game_data"]["countries"][name][side] == amount for name, amount in expected.items())


@pytest.mark.parametrize("card_id", [14, 28])
def test_unresolvable_opponent_influence_event_is_skipped_for_operations(card_id):
    from copy import deepcopy

    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    catalog = {card["id"]: card for card in load_standard_card_catalog()}
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    if card_id == 14:
        # US controls all seven listed spaces, leaving fewer than four COMECON targets.
        for name in ("E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria", "Yugoslavia"):
            countries[name]["us"] = data["countries"][name]["stability"]
    else:
        # Suez can remove at most two from each of three spaces, but only three US influence exist.
        countries["France"]["us"] = 1
        countries["U.K."]["us"] = 1
        countries["Israel"]["us"] = 1
    state = {
        "countries": countries,
        "tracks": {"defcon": 5, "victory_points": 0},
        "persistent_events": {},
    }

    result = resolve_card_event(
        state, deepcopy(catalog[card_id]), "us", mode="operations", country_data=data,
    )

    assert result["event_triggered"] is False
    assert result["game_data"]["countries"] == countries


def test_east_european_unrests_is_skipped_for_ops_when_too_few_targets_exist():
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    card = next(item for item in load_standard_card_catalog() if item["id"] == 29)
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    state = {"turn": 10, "countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    result = resolve_card_event(state, card, "ussr", mode="operations", country_data=data)

    assert result["event_triggered"] is False
    assert result["game_data"]["countries"] == countries


@pytest.mark.parametrize(
    ("card_id", "choices"),
    [
        (14, {"comecon": ["Poland", "Hungary", "Romania", "Canada"]}),
        (70, {"oas_founded": {"France": 2}}),
        (75, {"liberation_theology": {"Nicaragua": 3}}),
    ],
)
def test_selected_influence_event_rejects_invalid_choices(card_id, choices):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": {}, "tracks": {"defcon": 5, "victory_points": 0}}

    with pytest.raises(ValueError):
        resolve_card_event(
            state, card, "ussr" if card_id in {14, 75} else "us", mode="event",
            country_data=load_country_data(), event_choices=choices,
        )


@pytest.mark.parametrize(
    ("card_id", "faction", "starting", "choices", "expected"),
    [
        (74, "us", {"Egypt": {"us": 0, "ussr": 2}, "Iran": {"us": 0, "ussr": 1}, "Libya": {"us": 0, "ussr": 1}}, {"the_voice_of_america": {"Egypt": 2, "Iran": 1, "Libya": 1}}, {"Egypt": 0, "Iran": 0, "Libya": 0}),
        (88, "ussr", {"Lebanon": {"us": 2, "ussr": 0}, "Egypt": {"us": 1, "ussr": 0}, "Iran": {"us": 1, "ussr": 0}}, {"marine_barracks_bombing": {"Egypt": 1, "Iran": 1}}, {"Lebanon": 0, "Egypt": 0, "Iran": 0}),
    ],
)
def test_selected_influence_removal_events(card_id, faction, starting, choices, expected):
    from app.games.twilight_struggle.cards import load_standard_card_catalog
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries.update({name: dict(influence) for name, influence in starting.items()})
    card = next(item for item in load_standard_card_catalog() if item["id"] == card_id)
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}

    outcome = resolve_card_event(
        state, card, faction, mode="event", country_data=data, event_choices=choices,
    )

    for country, expected_us in expected.items():
        assert outcome["game_data"]["countries"][country]["us"] == expected_us
    if card_id == 74:
        assert outcome["game_data"]["countries"]["Egypt"]["ussr"] == 0


def test_scoring_card_dispatches_as_event_and_cannot_be_ops():
    from app.games.twilight_struggle.country_data import load_country_data

    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Japan"]["us"] = 4
    state = {"countries": countries, "tracks": {"defcon": 5, "victory_points": 0}}
    card = {"id": 1, "name": "Asia Scoring", "alignment": "both", "scoring": True}

    outcome = resolve_card_event(state, card, "us", mode="event", country_data=data)
    assert outcome["score_result"]["region"] == "Asia"
    assert outcome["game_data"]["tracks"]["victory_points"] == 4
    with pytest.raises(ValueError, match="must be played as events"):
        resolve_card_event(state, card, "us", mode="operations", country_data=data)
