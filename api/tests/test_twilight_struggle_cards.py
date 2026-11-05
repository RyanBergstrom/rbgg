from app.games.twilight_struggle.cards import load_standard_card_catalog, standard_deck


def test_standard_catalog_contains_only_base_ids_and_excludes_china_from_deck():
    catalog = load_standard_card_catalog()
    deck = standard_deck()

    assert len(catalog) == 110
    assert [card["id"] for card in catalog] == list(range(1, 111))
    assert all(card["id"] <= 110 for card in catalog)
    assert len(deck) == 109
    china = next(card for card in catalog if card["name"] == "The China Card")
    assert china["special"] is True
    assert china["deck_card"] is False
    assert all(card["deck_card"] for card in deck)


def test_era_decks_have_expected_metadata_and_scoring_cards():
    early = standard_deck(1)
    mid = standard_deck(2)
    late = standard_deck(3)

    assert all(card["era"] == 1 for card in early)
    assert all(card["era"] == 2 for card in mid)
    assert all(card["era"] == 3 for card in late)
    assert {card["name"] for card in early if card["scoring"]} == {
        "Asia Scoring", "Europe Scoring", "Middle East Scoring"
    }
    handlers = {card["name"]: card["effect_handler"] for card in early + mid + late}
    assert handlers["Duck and Cover"] == "duck_and_cover"
    assert handlers["Five Year Plan"] == "five_year_plan"
    assert handlers["Fidel*"] == "fidel"
    assert handlers["Romanian Abdication*"] == "romanian_abdication"
    assert handlers["COMECON*"] == "comecon"
    assert handlers["Nasser*"] == "nasser"
    assert handlers["De Gaule Leads France*"] == "de_gaulle_leads_france"
    assert handlers["Nuclear Test Ban"] == "nuclear_test_ban"
    assert handlers["Containment*"] == "containment"
    assert handlers["Red Scare/Purge"] == "red_scare_purge"
    assert handlers["How I Learned to Stop Worrying*"] == "how_i_learned_to_stop_worrying"
    assert handlers["Kitchen Debates*"] == "kitchen_debates"
    assert handlers["Brezhnev Doctrine*"] == "brezhnev_doctrine"
    assert handlers["Allende*"] == "allende"
    assert handlers["OAS Founded*"] == "oas_founded"
    assert handlers["Willy Brandt*"] == "willy_brandt"
    assert handlers["Panama Canal Returned*"] == "panama_canal_returned"
    assert handlers["Camp David Accords*"] == "camp_david_accords"
    assert handlers["Alliance For Progress*"] == "alliance_for_progress"
    assert handlers["Portuguese Empire Crumbles*"] == "portuguese_empire_crumbles"
    assert handlers["John Paul II Elected Pope*"] == "john_paul_ii_elected_pope"
    assert handlers["Sadat Expels Soviets*"] == "sadat_expels_soviets"
    assert handlers["The Voice of America"] == "the_voice_of_america"
    assert handlers["Liberation Theology"] == "liberation_theology"
    assert handlers["Iranian Hostage Crisis*"] == "iranian_hostage_crisis"
    assert handlers["The Iron Lady*"] == "the_iron_lady"
    assert handlers["Reagan Bombs Libya*"] == "reagan_bombs_libya"
    assert handlers["Marine Barracks Bombing*"] == "marine_barracks_bombing"
    assert handlers["Glasnost*"] == "glasnost"
    assert handlers['"An Evil Empire"*'] == "an_evil_empire"
    assert handlers["Pershing II Deployed*"] == "pershing_ii_deployed"
    assert handlers["Solidarity*"] == "solidarity"
    by_id = {card["id"]: card["effect_handler"] for card in early + mid + late}
    assert {card_id: by_id[card_id] for card_id in (19, 29, 30, 53, 63, 66)} == {
        19: "truman_doctrine",
        29: "east_european_unrests",
        30: "decolonization",
        53: "south_african_unrest",
        63: "colonial_rearguards",
        66: "puppet_governments",
    }
    assert {card_id: by_id[card_id] for card_id in (7, 16, 22, 28)} == {
        7: "socialist_governments",
        16: "warsaw_pact_formed",
        22: "independent_reds",
        28: "suez_crisis",
    }
    assert {card_id: by_id[card_id] for card_id in (39, 58, 61)} == {
        39: "arms_race",
        58: "cultural_revolution",
        61: "opec",
    }
    assert sum(handler is not None for handler in by_id.values()) == 102
    assert by_id[110] == "awacs_sale_to_saudis"
    assert {card_id: by_id[card_id] for card_id in (56, 57, 71, 92, 98)} == {
        56: "muslim_revolution",
        57: "abm_treaty",
        71: "nixon_plays_china",
        92: "terrorism",
        98: "aldrich_ames_remix",
    }
