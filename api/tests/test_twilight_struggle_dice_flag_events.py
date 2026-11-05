import pytest

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


class FixedRng:
    """Returns queued die values in order; mirrors random.Random.randint for d6."""

    def __init__(self, *values):
        self._values = list(values)

    def randint(self, low, high):
        value = self._values.pop(0)
        assert low <= value <= high
        return value


DATA = load_country_data()


def _state(defcon=5, influence=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    for name, values in (influence or {}).items():
        countries[name].update(values)
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": defcon, "military_operations": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "turn": 1,
    }


def _card(card_id, handler, name):
    return {"id": card_id, "name": name, "effect_handler": handler, "alignment": "ussr", "event_removed": False}


def _play(state, card_id, handler, name, phasing="ussr", rng=None, choices=None):
    return resolve_card_event(
        state,
        _card(card_id, handler, name),
        phasing,
        mode="event",
        country_data=DATA,
        rng=rng,
        event_choices=choices or {},
    )


def test_korean_war_success_replaces_us_influence_and_adds_ussr_military():
    state = _state(influence={"S. Korea": {"us": 2}})
    result = _play(state, 11, "korean_war", "Korean War", rng=FixedRng(6))
    game = result["game_data"]
    assert game["countries"]["S. Korea"] == {"us": 0, "ussr": 2}
    assert game["tracks"]["victory_points"] == -2
    assert game["tracks"]["military_operations"]["ussr"] == 2


def test_korean_war_failure_only_adds_military():
    state = _state(influence={"S. Korea": {"us": 2}})
    result = _play(state, 11, "korean_war", "Korean War", rng=FixedRng(3))
    game = result["game_data"]
    assert game["countries"]["S. Korea"] == {"us": 2, "ussr": 0}
    assert game["tracks"]["victory_points"] == 0
    assert game["tracks"]["military_operations"]["ussr"] == 2


def test_dice_events_require_server_rng():
    with pytest.raises(ValueError, match="server RNG"):
        _play(_state(), 11, "korean_war", "Korean War", rng=None)


def test_arab_israeli_war_blocked_after_camp_david():
    state = _state()
    state["persistent_events"]["arab_israeli_war_cancelled"] = True
    with pytest.raises(ValueError, match="Camp David"):
        _play(state, 13, "arab_israeli_war", "Arab-Israeli War", rng=FixedRng(6))


def test_indo_pakistani_war_requires_valid_target():
    with pytest.raises(ValueError, match="India or Pakistan"):
        _play(_state(), 24, "indo_pakistani_war", "Indo-Pakistani War", rng=FixedRng(6), choices={})


def test_indo_pakistani_war_success_gives_phasing_player_vp_and_influence():
    state = _state(influence={"India": {"us": 1}})
    result = _play(
        state, 24, "indo_pakistani_war", "Indo-Pakistani War",
        rng=FixedRng(6), choices={"indo_pakistani_war": "India"},
    )
    game = result["game_data"]
    assert game["countries"]["India"] == {"us": 0, "ussr": 1}
    assert game["tracks"]["victory_points"] == -2


def test_brush_war_rejects_high_stability_target():
    with pytest.raises(ValueError, match="stability 1 or 2"):
        _play(_state(), 36, "brush_war", "Brush War", rng=FixedRng(6), choices={"brush_war": "W. Germany"})


def _low_stability_europe_target():
    candidates = [
        name for name, info in DATA["countries"].items()
        if info.get("region") == "Europe" and info.get("stability") in {1, 2}
    ]
    assert candidates, "expected at least one Europe country with stability 1 or 2"
    return candidates[0]


def test_brush_war_blocked_on_us_controlled_europe_under_nato():
    target = _low_stability_europe_target()
    state = _state(influence={target: {"us": 5}})
    state["persistent_events"]["nato"] = {"faction": "us", "expires_turn": 10}
    with pytest.raises(ValueError, match="NATO"):
        _play(state, 36, "brush_war", "Brush War", rng=FixedRng(6), choices={"brush_war": target})


def test_brush_war_allowed_on_us_controlled_europe_after_nato_cancelled():
    target = _low_stability_europe_target()
    state = _state(influence={target: {"us": 5}})
    state["persistent_events"]["nato"] = {"faction": "us", "expires_turn": 10}
    state["persistent_events"]["nato_cancelled_countries"] = [target]
    result = _play(state, 36, "brush_war", "Brush War", rng=FixedRng(6), choices={"brush_war": target})
    assert result["game_data"]["tracks"]["military_operations"]["ussr"] == 3


def test_summit_tie_changes_nothing():
    state = _state()
    result = _play(state, 45, "summit", "Summit", phasing="us", rng=FixedRng(4, 4))
    game = result["game_data"]
    assert game["tracks"]["victory_points"] == 0
    assert game["tracks"]["defcon"] == 5


def test_summit_high_roller_gains_vp_and_optional_defcon_move():
    state = _state(defcon=4)
    result = _play(
        state, 45, "summit", "Summit", phasing="us",
        rng=FixedRng(6, 1), choices={"summit_defcon": -1},
    )
    game = result["game_data"]
    assert game["tracks"]["victory_points"] == 2
    assert game["tracks"]["defcon"] == 3


def test_cuban_missile_crisis_sets_defcon_two_and_records_flag():
    result = _play(_state(defcon=5), 40, "cuban_missile_crisis", "Cuban Missile Crisis", phasing="us")
    game = result["game_data"]
    assert game["tracks"]["defcon"] == 2
    assert game["persistent_events"]["cuban_missile_crisis"] == {"faction": "ussr", "expires_turn": 1}


def test_tear_down_this_wall_places_influence_and_cancels_willy_brandt():
    result = _play(_state(), 96, "tear_down_this_wall", "Tear Down This Wall", phasing="us")
    game = result["game_data"]
    assert game["countries"]["E. Germany"]["us"] == 3
    assert game["persistent_events"]["tear_down_this_wall"] is True


def test_junta_requires_central_or_south_american_country():
    with pytest.raises(ValueError, match="Central or South American"):
        _play(_state(), 47, "junta", "Junta", phasing="us", choices={"junta": "France"})


def test_junta_places_two_influence_for_phasing_player():
    result = _play(_state(), 47, "junta", "Junta", phasing="us", choices={"junta": "Argentina"})
    assert result["game_data"]["countries"]["Argentina"]["us"] == 2


def test_ortega_removes_all_us_influence_from_nicaragua():
    state = _state(influence={"Nicaragua": {"us": 3}})
    result = _play(state, 91, "ortega_nicaragua", "Ortega Wins the Nicaraguan Revolution")
    assert result["game_data"]["countries"]["Nicaragua"]["us"] == 0


def test_chernobyl_requires_known_region_and_records_flag():
    with pytest.raises(ValueError, match="major region"):
        _play(_state(), 94, "chernobyl", "Chernobyl", phasing="us", choices={"chernobyl": "Moon"})
    result = _play(_state(), 94, "chernobyl", "Chernobyl", phasing="us", choices={"chernobyl": "Europe"})
    assert result["game_data"]["persistent_events"]["chernobyl"]["region"] == "Europe"


@pytest.mark.parametrize(
    ("card_id", "handler", "flag", "expected"),
    [
        (27, "us_japan_pact", "us_japan_pact", True),
        (41, "nuclear_subs", "nuclear_subs", {"faction": "us", "expires_turn": 1}),
        (69, "latin_american_death_squads", "latin_american_death_squads", {"faction": "ussr", "expires_turn": 1}),
        (93, "iran_contra_scandal", "iran_contra_scandal", {"faction": "ussr", "expires_turn": 1}),
    ],
)
def test_flag_events_record_persistent_flags(card_id, handler, flag, expected):
    result = _play(_state(), card_id, handler, handler, phasing="ussr")
    assert result["game_data"]["persistent_events"][flag] == expected
    assert result["event_triggered"] is True
