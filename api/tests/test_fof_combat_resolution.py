import pytest

from app.games.fields_of_fire.action_deck import ACTION_CARD_IDS, get_action_card
from app.games.fields_of_fire.combat_resolution import (
    parse_combat_resolution,
    resolve_combat,
)


def test_every_action_card_parses_to_full_table():
    for card_id in ACTION_CARD_IDS:
        text = get_action_card(card_id)["action_details"]["combat_resolution"]
        table = parse_combat_resolution(text)
        assert sorted(table) == list(range(-4, 7))
        assert set(table.values()) <= {"HIT", "PIN", "MISS"}


def test_known_card_values_match_printed_column():
    # A01: all MISS. A02: -4 PIN, rest MISS. A33: HIT up to 0, PIN at +1..+4.
    assert resolve_combat(get_action_card("FOF-ACTION-001")["action_details"]["combat_resolution"], 0) == "MISS"
    a02 = get_action_card("FOF-ACTION-002")["action_details"]["combat_resolution"]
    assert resolve_combat(a02, -4) == "PIN"
    assert resolve_combat(a02, -3) == "MISS"
    a33 = get_action_card("FOF-ACTION-033")["action_details"]["combat_resolution"]
    assert resolve_combat(a33, 0) == "HIT"
    assert resolve_combat(a33, 1) == "PIN"
    assert resolve_combat(a33, 5) == "MISS"


def test_modifiers_outside_printed_range_use_nearest_value():
    text = get_action_card("FOF-ACTION-033")["action_details"]["combat_resolution"]
    assert resolve_combat(text, -9) == resolve_combat(text, -4) == "HIT"
    assert resolve_combat(text, 12) == resolve_combat(text, 6) == "MISS"


def test_malformed_column_is_rejected():
    with pytest.raises(ValueError):
        parse_combat_resolution("-4 HIT; -3 HIT")  # incomplete
    with pytest.raises(ValueError):
        parse_combat_resolution("-4 WOUND; " + "; ".join(f"{m} MISS" for m in range(-3, 7)))
    with pytest.raises(ValueError):
        parse_combat_resolution("-4 HIT; -4 MISS; " + "; ".join(f"{m} MISS" for m in range(-3, 7)))
