import pytest

from app.games.fields_of_fire.action_deck import (
    ACTION_CARD_IDS,
    RESHUFFLE_CARD,
    draw,
    force_next,
    get_action_card,
    new_action_deck,
)
from app.games.fields_of_fire.validator import FieldsOfFireValidator


def _all_cards(deck):
    return sorted(deck["draw_pile"] + deck["discard"])


def test_new_deck_has_50_action_cards_and_reshuffle_card():
    deck = new_action_deck(seed=1)
    assert _all_cards(deck) == sorted(ACTION_CARD_IDS + [RESHUFFLE_CARD])


def test_same_seed_gives_same_order():
    assert new_action_deck(seed=7)["draw_pile"] == new_action_deck(seed=7)["draw_pile"]


def test_draw_takes_full_count_and_discards_drawn_cards():
    deck = new_action_deck(seed=2)
    cards = draw(deck, 3, reason="test")
    assert len(cards) == 3
    assert RESHUFFLE_CARD not in cards
    assert set(cards) <= set(deck["discard"])
    assert deck["log"][-1] == {"reason": "test", "cards": cards, "reshuffled": False}


def test_forced_cards_are_drawn_in_order():
    deck = new_action_deck(seed=3)
    force_next(deck, ["FOF-ACTION-005", "FOF-ACTION-009"])
    assert draw(deck, 2) == ["FOF-ACTION-005", "FOF-ACTION-009"]


def test_reshuffle_card_completes_draw_then_reshuffles_everything():
    deck = new_action_deck(seed=4)
    force_next(deck, [RESHUFFLE_CARD, "FOF-ACTION-001", "FOF-ACTION-002"])
    cards = draw(deck, 2, reason="reshuffle")
    # Reshuffle card does not count; the full two cards are still drawn.
    assert cards == ["FOF-ACTION-001", "FOF-ACTION-002"]
    assert deck["log"][-1]["reshuffled"] is True
    # After reshuffle the whole deck (including the reshuffle card) is back in the draw pile.
    assert deck["discard"] == []
    assert _all_cards(deck) == sorted(ACTION_CARD_IDS + [RESHUFFLE_CARD])
    assert deck["shuffle_count"] >= 2


def test_forced_unknown_card_is_rejected():
    deck = new_action_deck()
    with pytest.raises(ValueError):
        force_next(deck, ["FOF-ACTION-999"])


def test_initial_game_data_contains_seeded_action_deck():
    gd = FieldsOfFireValidator().initial_game_data()
    deck = gd["action_deck"]
    assert deck["seed"] == 0
    assert _all_cards(deck) == sorted(ACTION_CARD_IDS + [RESHUFFLE_CARD])

def test_deck_uses_all_reviewed_action_cards_from_final_file():
    assert len(ACTION_CARD_IDS) == 50
    assert ACTION_CARD_IDS[0] == "FOF-ACTION-001"
    assert ACTION_CARD_IDS[-1] == "FOF-ACTION-050"
    for card_id in ACTION_CARD_IDS:
        card = get_action_card(card_id)
        assert card["classification"]["reviewed"] is True
        assert card["action_details"]["card_number"] >= 1


def test_reshuffle_card_is_from_final_file():
    assert RESHUFFLE_CARD == "FOF-ACTION-RESHUFFLE-CARD"
    assert get_action_card(RESHUFFLE_CARD)["card_type"] == "action"
