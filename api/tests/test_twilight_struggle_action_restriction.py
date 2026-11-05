import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


class _FixedRoll:
    """Deterministic stand-in for server RNG: every d6 roll returns ``value``."""

    def __init__(self, value: int):
        self.value = value

    def randint(self, low: int, high: int) -> int:
        assert (low, high) == (1, 6)
        return self.value


def _game(**overrides):
    game = {
        "turn": 2,
        "current_phase": "action_round",
        "current_player_faction": "us",
        "player_by_faction": {"us": "player_1", "ussr": "player_2"},
        "hands": {
            "us": [
                {"id": 25, "name": "Containment", "operations": 3, "alignment": "us", "effect_handler": "containment"},
                {"id": 20, "name": "Filler", "operations": 3, "alignment": "us"},
            ],
            "ussr": [],
        },
        "actions_taken": {"us": 0, "ussr": 0},
        "action_round": 0,
        "countries": {},
        "tracks": {"defcon": 5, "victory_points": 0, "space_race": {"us": 0, "ussr": 0}},
        "persistent_events": {"action_restriction": {"faction": "us", "expires_turn": 2, "scoring_only": False}},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }
    game.update(overrides)
    return game


def test_quagmire_sets_restriction_on_opponent_until_end_of_turn():
    card = {"id": 42, "name": "Quagmire", "alignment": "ussr", "effect_handler": "quagmire"}
    result = resolve_card_event(_game(persistent_events={}), card, "ussr", mode="event")
    assert result["event_triggered"] is True
    assert result["game_data"]["persistent_events"]["action_restriction"] == {
        "faction": "us",
        "expires_turn": 2,
        "scoring_only": False,
        "source": "quagmire",
    }


def test_quagmire_cancels_active_norad_effect():
    card = {"id": 42, "name": "Quagmire", "alignment": "ussr", "effect_handler": "quagmire"}
    game = _game(persistent_events={"norad": {"faction": "us", "expires_turn": 2}})
    result = resolve_card_event(game, card, "ussr", mode="event")
    assert "norad" not in result["game_data"]["persistent_events"]
    assert result["game_data"]["persistent_events"]["action_restriction"]["source"] == "quagmire"
    assert "norad" in game["persistent_events"]


def test_bear_trap_sets_restriction_on_ussr():
    card = {"id": 44, "name": "Bear Trap", "alignment": "us", "effect_handler": "bear_trap"}
    result = resolve_card_event(_game(persistent_events={}), card, "us", mode="event")
    assert result["game_data"]["persistent_events"]["action_restriction"]["faction"] == "ussr"


def test_restricted_play_without_discard_is_rejected():
    with pytest.raises(ValueError, match="discard"):
        play_card_action(_game(), "us", 25, "event", rng=_FixedRoll(1), country_data=load_country_data())


def test_restricted_play_with_successful_roll_discards_and_plays_card():
    game = _game()
    result = play_card_action(
        game, "us", 25, "event",
        restriction_discard_id=20, rng=_FixedRoll(4), country_data=load_country_data(),
    )
    assert "action_restriction" not in result["persistent_events"]
    assert [c["id"] for c in result["discard_pile"]] == [20, 25]
    assert result["hands"]["us"] == []
    assert result["actions_taken"]["us"] == 1
    assert result["last_card_play"]["card_id"] == 25
    # Caller state is untouched (atomic).
    assert "action_restriction" in game["persistent_events"]


def test_restricted_play_with_failed_roll_spends_round_without_playing_card():
    result = play_card_action(
        _game(), "us", 25, "event",
        restriction_discard_id=20, rng=_FixedRoll(5), country_data=load_country_data(),
    )
    assert result["persistent_events"]["action_restriction"]["faction"] == "us"
    assert [c["id"] for c in result["hands"]["us"]] == [25]
    assert [c["id"] for c in result["discard_pile"]] == [20]
    assert result["actions_taken"]["us"] == 1
    assert result["last_card_play"]["restriction"] == {"reason": "failed_roll", "roll": 5}
    assert "containment" not in result["persistent_events"]


def test_restriction_without_eligible_discard_limits_faction_to_scoring_cards():
    game = _game(hands={"us": [{"id": 25, "name": "Containment", "operations": 3, "alignment": "us", "effect_handler": "containment"}], "ussr": []})
    result = play_card_action(game, "us", 25, "event", rng=_FixedRoll(1), country_data=load_country_data())
    assert result["persistent_events"]["action_restriction"]["scoring_only"] is True
    assert result["actions_taken"]["us"] == 1
    assert [c["id"] for c in result["hands"]["us"]] == [25]
    with pytest.raises(ValueError, match="scoring cards"):
        play_card_action(result, "us", 25, "event", rng=_FixedRoll(1), country_data=load_country_data())


def test_scoring_only_restriction_without_scoring_card_closes_remaining_action_rounds():
    from app.games.twilight_struggle.action_rounds import execute_action_round
    from app.games.twilight_struggle.turns import faction_can_act

    game = _game(
        hands={"us": [{"id": 25, "name": "Containment", "operations": 3, "alignment": "us", "effect_handler": "containment"}], "ussr": []},
    )
    result = execute_action_round(
        {"game_data": game, "rng_seed": 1, "rng_state_json": "{}"},
        "us", 25, "event", country_data=load_country_data(),
    )

    assert result["game_data"]["persistent_events"]["action_restriction"]["scoring_only"] is True
    assert faction_can_act(result["game_data"], "us") is False
    assert result["game_data"]["current_phase"] == "turn_end"


def test_restriction_does_not_affect_the_other_faction():
    game = _game(
        current_player_faction="ussr",
        hands={"us": [], "ussr": [{"id": 25, "name": "Containment", "operations": 3, "alignment": "us", "effect_handler": "containment"}]},
    )
    result = play_card_action(game, "ussr", 25, "event", rng=_FixedRoll(1), country_data=load_country_data())
    assert result["persistent_events"]["action_restriction"]["faction"] == "us"
    assert result["actions_taken"]["ussr"] == 1
